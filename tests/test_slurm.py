"""roach.slurm: the parts that are pure functions.

What is checked: what would go wrong silently or only on the compute node. A
mistake sbatch or submit() rejects out loud is not tested here.
"""

import inspect
import re
import subprocess
from importlib.resources import files

import pytest

from roach.slurm import Resources, timestamp
from roach.slurm._submit import fill, home, launch, on_cluster
from roach.slurm._submit import submit as submit_fn
from roach.slurm.clusters.aws import AWS
from roach.slurm.clusters.ilc import ILC
from roach.slurm.clusters.marlowe import MARLOWE


def test_timestamp_has_no_characters_that_break_wandb_or_cargo():
    t = timestamp()
    assert ":" not in t and "/" not in t


def ampere(**over) -> Resources:
    kwargs = dict(
        partition="il",
        account="infolab",
        qos="il",
        time="7-00:00:00",
        gpus="a100:8",
        cpus_per_task=16,
        ntasks=None,
        exclusive=True,
        mem=None,
        mem_per_gpu=None,
        constraint="ampere",
        nodelist=None,
        reservation=None,
        dependency=None,
    )
    return Resources(**{**kwargs, **over})


def scripts() -> dict[str, str]:
    """Every shell file that reaches a compute node, by name."""
    return {
        "bootstrap.sh": files("roach.slurm").joinpath("bootstrap.sh").read_text(),
        "node.sh": files("roach.slurm").joinpath("node.sh").read_text(),
        "ilc.site.sh": ILC.site.read_text(),
        "marlowe.site.sh": MARLOWE.site.read_text(),
        "aws.site.sh": AWS.site.read_text(),
    }


def test_a_cpu_only_stage_asks_for_no_gpu():
    """A pipeline stage that does not use an accelerator must not hold one. GPUs
    are the scarcest thing on these nodes, so a cpu-only job that keeps one idle
    caps how many of its siblings can run -- which is a throughput bug that
    looks like a scheduling one."""
    flags = ampere(gpus="0").sbatch_flags()
    assert not [f for f in flags if f.startswith("--gres")]
    assert "--ntasks-per-node=1" in flags
    assert ampere(gpus="0").ranks == 1
    with pytest.raises(ValueError, match="no GPUs is"):
        ampere(gpus="a100:0")


def test_ntasks_overrides_one_rank_per_gpu():
    """One rank per GPU is what DDP wants, not a law. A stage that parallelises
    inside one process -- sentence-transformers spawning a worker per device --
    needs every GPU visible to a single rank, and got one GPU each instead."""
    r = ampere(gpus="10", ntasks=1)
    assert r.ranks == 1
    assert "--ntasks-per-node=1" in r.sbatch_flags()
    assert "--gres=gpu:10" in r.sbatch_flags()
    with pytest.raises(ValueError, match="ntasks must be"):
        ampere(ntasks=0)


def test_sbatch_flags():
    flags = ampere().sbatch_flags()
    assert "--ntasks-per-node=8" in flags
    assert "--gres=gpu:a100:8" in flags
    assert "--cpus-per-task=16" in flags
    assert "--exclusive" in flags
    assert not any(f.startswith("--mem") for f in flags)
    assert "--mem=1500000M" in ampere(mem="1500000M").sbatch_flags()


def test_every_placeholder_in_the_scripts_is_one_submit_fills():
    """A placeholder nobody fills reaches the compute node as a literal @NAME@,
    and fails there rather than here."""

    used = set()
    for text in scripts().values():
        used |= set(re.findall(r"@[A-Z_]+@", text))
    filled = set(re.findall(r'"(@[A-Z_]+@)"', inspect.getsource(submit_fn)))
    # Subset, not equality: submit() also fills placeholders that only reach the
    # script through another one (@TARGET@ and @ARGS@ ride inside @LAUNCH@).
    assert used <= filled


def test_no_placeholder_sits_inside_a_comment():
    """`setup` is spliced in verbatim, one command per line. A placeholder named
    in a comment gets the same treatment: the first line stays commented out and
    every line after it breaks out and runs as garbage -- which is a two-command
    setup silently corrupted, and a single-command one working fine."""

    for name, text in scripts().items():
        bad = [
            line
            for line in text.splitlines()
            if line.lstrip().startswith("#") and re.search(r"@[A-Z_]+@", line)
        ]
        assert not bad, f"{name}: {bad}"


def test_the_job_scripts_take_no_configuration_from_the_environment():
    """A job's environment is what submit() put there. A ``${VAR:-default}`` is
    a knob nobody passed, silently answered by whatever the node exported --
    which is how the same submission produces two different runs."""

    # who we are, and what slurm tells the job about itself: not configuration
    runtime = {"USER", "SLURM_RESTART_COUNT", "SLURM_JOB_ID", "SLURM_PROCID"}
    for name, text in scripts().items():
        read = set(re.findall(r"\$\{([A-Z_]+):-", text))
        assert read <= runtime, f"{name} reads {sorted(read - runtime)} from the env"


def test_job_env_is_not_inherited():
    """--export=ALL is sbatch's default and would copy this shell's home, PATH
    and API tokens into the job (and slurm's job record); the batch script
    carries everything it needs."""
    assert '"--export=NONE"' in inspect.getsource(submit_fn)


def test_the_launcher_lets_srun_inherit_the_job_environment():
    """--export=NONE (which keeps the submit shell out of the job) also stops
    srun from passing the job's own environment to its tasks, so `pixi` is not
    on their PATH; SLURM_EXPORT_ENV=ALL puts it back."""
    assert "--export=ALL" in launch(ampere(), "pkg:main", "/args.json", "default", overlap=False)


def test_the_core_knows_no_cluster_and_no_project():
    """Everything cluster-specific lives under `clusters/`, and nothing
    project-specific lives anywhere: a node name, a qos, a build cache or a
    framework's scratch file in the core is a job on some other cluster or
    project silently inheriting it."""
    core = [
        p
        for p in files("roach.slurm").iterdir()
        if p.name.endswith((".py", ".sh")) and p.name != "__init__.py"  # the usage example
    ]
    words = ("blackwell", "ampere", "infolab", "il-lo", "/lfs/", "/dfs/", "cargo_target", "/dev/shm",
             "h100", "m000137", "/fsx", "parallelcluster", "/opt/slurm", "/users/", "local_scratch", "/cm/shared")
    for p in core:
        text = p.read_text().lower()
        hit = [w for w in words if w in text]
        assert not hit, f"{p.name} mentions {hit}"


def test_a_dependent_job_is_cancelled_when_its_dependency_fails():
    """`after` chains a pipeline's stages in one submission pass. Without
    --kill-on-invalid-dep the second stage of a failed first stage sits PENDING
    forever, which looks like a slow queue rather than a failure."""
    src = inspect.getsource(submit_fn)
    assert '"--dependency=afterok:{after}"' in src or "--dependency=afterok:" in src
    assert "--kill-on-invalid-dep=yes" in src


def test_mem_per_gpu_is_how_a_job_gets_a_whole_node_of_gpus():
    """A partition with DefMemPerGPU applies it when deciding whether a job
    fits, and --mem does not displace it: the most GPUs a job can hold becomes
    RealMemory / DefMemPerGPU however little memory it wants. Here that is 3
    GPUs on a 770G node. --mem-per-gpu replaces the default and lifts it."""
    flags = ampere(gpus="8", mem=None, mem_per_gpu="20G").sbatch_flags()
    assert "--mem-per-gpu=20G" in flags
    assert not [f for f in flags if f.startswith("--mem=")]
    with pytest.raises(ValueError, match="not both"):
        ampere(mem="10G", mem_per_gpu="10G")


def test_a_tilde_path_is_the_clusters_home_not_this_one():
    """Paths are strings for the cluster; expanding ``~`` here would name
    this machine's home on a cluster that has a different one."""
    assert home("~/scratch/x") == "$HOME/scratch/x"
    assert home("~") == "$HOME"
    assert home("/abs/x") == "/abs/x"
    assert home("x~/y") == "x~/y"
    assert "expanduser" not in inspect.getsource(home)


def test_the_clone_root_is_made_after_the_env_sets_home():
    """`~/roach_clones` is `$HOME/roach_clones`, and HOME is wrong until the
    cluster's env has set it."""
    text = scripts()["bootstrap.sh"]
    assert text.index("roach_node_env\n") < text.index('mkdir -p "@CLONE_ROOT@"')


def test_a_remote_cluster_is_reached_over_ssh_in_batch_mode(monkeypatch):
    """Nothing interactive: a host that wants a password or Duo fails at once
    instead of hanging a submission."""
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["env"] = kw["env"]
        return subprocess.CompletedProcess(cmd, 0, stdout="Submitted batch job 7\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("SLURM_JOB_ID", "1")
    assert on_cluster(MARLOWE, "sbatch x") == "Submitted batch job 7\n"
    assert seen["cmd"][:3] == ["ssh", "-o", "BatchMode=yes"]
    assert seen["cmd"][3] == "marlowe"
    assert seen["cmd"][4] == "sbatch x"
    assert "SLURM_JOB_ID" not in seen["env"]
    assert on_cluster(ILC, "true") == "Submitted batch job 7\n"
    assert seen["cmd"] == ["bash", "-c", "true"]


def test_the_launcher_spells_out_the_shape_and_overlaps_only_inside_a_hold():
    """Inside a held allocation the ranks start from a one-task step, whose
    SLURM_NTASKS would otherwise size them."""
    plain = launch(ampere(), "pkg:main", "/a.json", "default", overlap=False)
    held = launch(ampere(), "pkg:main", "/a.json", "default", overlap=True)
    for line in (plain, held):
        assert "--nodes=1 --ntasks=8 --ntasks-per-node=8 --cpus-per-task=16" in line
    assert "--overlap" not in plain and "--overlap" in held


def test_a_placeholder_inside_a_spliced_piece_is_filled_too():
    """node.sh reaches the script through @ENV@ and names @SECRETS_DIR@ itself;
    a single pass in dict order left it literal on the node."""
    out = fill("a @ENV@ c", {"@SECRETS_DIR@": "/s", "@ENV@": "cat @SECRETS_DIR@/github"})
    assert out == "a cat /s/github c"
