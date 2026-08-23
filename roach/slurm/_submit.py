"""Submit a python function to slurm.

The submitting side owns everything that needs the repo: it refuses a dirty or
unpushed tree, records the commit, checks the arguments against the target's
signature, and hands slurm a script that reproduces the run from that commit.
Nothing here is site-specific: what is comes in as `cluster`, and paths,
account and QOS are arguments.
"""

import inspect
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, get_type_hints

from beartype.door import die_if_unbearable

import roach

from roach.slurm.clusters import Cluster
from roach.slurm.resources import Resources
from roach.slurm.target import resolve


def timestamp() -> str:
    """Unique run id: ``yy-mm-dd_hh-mm-ss_ns``.

    Punctuated with ``-`` rather than ``:``: the id names a wandb run (which
    rejects ``:``), an output directory, and a build path (cargo fails under a
    ``:``).
    """
    now = time.time_ns()
    return f"{datetime.fromtimestamp(now / 1e9):%y-%m-%d_%H-%M-%S}_{now % 1_000_000_000:09d}"


@dataclass(frozen=True)
class Job:
    id: str
    run_id: str
    log: str
    """The log's path as the cluster sees it: ``~`` is left for the cluster's
    home, which may not be this machine's."""
    target: str
    cluster: Cluster

    @property
    def state(self) -> str:
        out = on_cluster(self.cluster, f"sacct -j {self.id} -n --format=State")
        return out.split("\n")[0].strip() or "UNKNOWN"


def home(path: Path | str) -> str:
    """A path for the cluster: a leading ``~`` becomes ``$HOME``, expanded by
    the shell there -- on the submit host and, in the batch script, after the
    cluster's env has set the job's HOME. Never expanded here: this machine's
    home is not the cluster's."""
    path = str(path)
    if path == "~" or path.startswith("~/"):
        return "$HOME" + path[1:]
    return path


def on_cluster(cluster: Cluster, script: str, stdin: str | None = None) -> str:
    """Run a shell snippet where the cluster's slurm commands work and return
    its stdout: here when the cluster has no `submit_host`, else over ssh.
    Nothing from this process's SLURM_*/SBATCH_* reaches it: submitting from
    inside an allocation would otherwise impose that job's shape."""
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("SLURM_", "SBATCH_"))
    }
    if cluster.submit_host is None:
        cmd = ["bash", "-c", script]
    else:
        cmd = ["ssh", "-o", "BatchMode=yes", cluster.submit_host, script]
    out = subprocess.run(cmd, input=stdin, capture_output=True, text=True, env=env)
    if out.returncode:
        where = cluster.submit_host or "here"
        raise RuntimeError(f"{where}: `{script}` failed ({out.returncode}):\n{out.stderr}")
    return out.stdout


def check_args(target: str, args: dict[str, Any]) -> None:
    """Fail here rather than forty minutes into a job.

    Missing and unknown arguments are caught by name; the values are checked
    against the target's annotations by beartype, so a str where a list of ints
    belongs is a submit-time error too.
    """
    fn = resolve(target)
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)

    unknown = sorted(set(args) - set(sig.parameters))
    if unknown:
        raise TypeError(f"{target} takes no argument(s): {', '.join(unknown)}")
    missing = sorted(
        name
        for name, p in sig.parameters.items()
        if name not in args and p.default is inspect.Parameter.empty
    )
    if missing:
        raise TypeError(f"{target} is missing argument(s): {', '.join(missing)}")
    for name, value in args.items():
        if name in hints:
            try:
                die_if_unbearable(value, hints[name])
            except Exception as e:
                raise TypeError(f"{target}({name}=...): {e}") from None


def preflight(root: Path | str | None = None) -> tuple[str, str, str]:
    """(repo url, commit, branch) of a clean, pushed tree -- the job clones that."""
    if root is not None:
        os.chdir(root)
    root = _git("rev-parse", "--show-toplevel")
    if _git("status", "--porcelain"):
        raise RuntimeError(f"{root}: working tree is dirty; commit or stash first")
    repo = _git("remote", "get-url", "origin")
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    _git("fetch", "--quiet", "origin")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, f"origin/{branch}"]
    ).returncode:
        raise RuntimeError(f"{commit} is not on origin/{branch}; push first")
    return repo, commit, branch


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def launch(
    resources: Resources, target: str, args_path: str, pixi_env: str, overlap: bool
) -> str:
    """The srun line that starts the ranks, spliced into the batch script.

    `--export=ALL`. There is one rule, applied at two layers: **nothing from the
    submitting shell, everything from the job's own environment.** This srun is
    the second layer -- it runs *inside* the job, after env.sh has built the
    node-local HOME, the caches, the PATH to pixi and the tokens, and without
    ALL it would start the ranks nearly empty and find none of it. The
    `sbatch --export=NONE` that crosses from the submitting shell is the first
    layer, and says the opposite for the same reason: that shell's HOME does not
    exist on the node and its environment holds API tokens slurm would record.

    `--frozen`: the clone is shared, so a rank that re-solved would rewrite
    pixi.lock underneath every other job at this commit.

    `--chdir`: srun otherwise hands the tasks this shell's *resolved* cwd, and
    the clone root may be a per-node symlink into a host-specific path, so on
    a multi-node job every rank would be sent to the batch node's path -- which
    does not exist on any other node. `$REPO_DIR` is the unresolved one, and
    each node resolves it to its own disk.
    """
    run = (
        f"pixi run --frozen -e {pixi_env} python -m roach.slurm.run "
        f'"{target}" "{args_path}"'
    )
    # The shape is spelled out rather than taken from the environment: inside
    # a held allocation this srun runs from a one-task step whose SLURM_NTASKS
    # would otherwise size it, and --overlap lets it share the node with that
    # step.
    # --ntasks as well as --nodes: from inside a one-node step, slurm clamps
    # a --nodes=N request to that node unless the task count forces N.
    shape = (
        f"--nodes={resources.nodes} --ntasks={resources.ranks} "
        f"--ntasks-per-node={resources.ranks_per_node} "
        f"--cpus-per-task={resources.cpus_per_task}"
    )
    if overlap:
        shape += " --overlap"
    return (
        f"srun --export=ALL --chdir=$REPO_DIR --label --kill-on-bad-exit=1 {shape} \\\n"
        f"    {run}"
    )


def submit(
    target: str,
    args: dict[str, Any],
    resources: Resources,
    *,
    cluster: Cluster,
    name: str,
    repo_root: Path | str,
    log_root: Path | str,
    clone_root: Path | str,
    secrets_dir: Path | str,
    job_env: Path | str | None = None,
    setup: tuple[str, ...] = (),
    run_id: str | None = None,
    after: str | None = None,
    pixi_env: str = "default",
    inside: str | None = None,
) -> Job:
    """Run ``target(**args)`` on ``resources`` of ``cluster``, one rank per GPU.

    ``job_env`` is a shell file of the project's own (a path relative to
    ``repo_root`` works), sourced right after the cluster's environment on
    every node the job holds and before the clone is built: caches a build wants, limits a run wants, whatever is the project's
    business and not the cluster's. ``setup`` is different: it runs once per
    clone, after ``pixi install``, and is for building what the environment
    does not.

    ``run_id`` is minted here and injected into ``args`` if the target declares
    it; pass one to relaunch an existing run, which is how a run resumes from a
    checkpoint it wrote earlier.

    ``after`` is the id of a job this one waits for, so a pipeline whose stages
    want different hardware can be submitted in one pass instead of polling for
    the first stage to finish. The wait is on success: if the dependency fails,
    slurm cancels this job rather than leaving it pending forever.

    ``cluster.grace_secs`` before the wall clock the ranks are told to stop, so
    the job can checkpoint and requeue itself instead of ending as TIMEOUT (see
    bootstrap.sh).

    ``inside`` is the id of an allocation held with `hold()`: the run starts
    there now, as a step, instead of queueing as a job of its own. The script
    is the same one sbatch would get; it is written next to the logs and run
    by a detached one-task `srun --overlap`, and the ranks' srun overlaps it.
    Nothing requeues a step -- the wall clock is the holder's -- so this is
    for iterating, not for a run that must outlive the allocation.
    """
    # The repo and job_env are read here; every other path is the cluster's,
    # and a leading ``~`` in it means the cluster's home (see `home`).
    repo_root = Path(repo_root).expanduser()
    log_root, clone_root, secrets_dir = (home(p) for p in (log_root, clone_root, secrets_dir))
    os.chdir(repo_root)
    # The job runs from the repo root, so targets are importable relative to it
    # (examples.foo:main). Match that here, or the submit-time check would fail
    # on targets the job can import perfectly well.
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    repo, commit, _branch = preflight()
    run_id = run_id or timestamp()
    if "run_id" in inspect.signature(resolve(target)).parameters:
        args = {**args, "run_id": run_id}
    check_args(target, args)

    args_path = f"{log_root}/{run_id}.args.json"
    on_cluster(
        cluster,
        f'mkdir -p "{log_root}" && cat > "{args_path}"',
        stdin=json.dumps(args, indent=1, sort_keys=True) + "\n",
    )

    script = files("roach.slurm").joinpath("bootstrap.sh").read_text()
    env_sh = cluster.env.read_text()
    job_env_sh = Path(job_env).expanduser().read_text() if job_env else ""
    for key, value in {
        "@REPO@": repo,
        "@COMMIT@": commit,
        "@RUN_ID@": run_id,
        "@NAME@": name,
        "@TARGET@": target,
        "@ROACH@": roach.__version__,
        "@ARGS@": args_path,
        "@LOG_ROOT@": log_root,
        "@CLONE_ROOT@": clone_root,
        "@SECRETS_DIR@": secrets_dir,
        "@SETUP@": "\n".join(setup),
        "@NODES@": str(resources.nodes),
        "@INSIDE@": "1" if inside is not None else "0",
        "@ENV@": env_sh,
        "@JOB_ENV@": job_env_sh,
        "@LAUNCH@": launch(resources, target, args_path, pixi_env, overlap=inside is not None),
    }.items():
        script = script.replace(key, value)

    if inside is not None:
        assert after is None, "a step inside a held allocation cannot wait on a job"
        log = f"{log_root}/{run_id}_{inside}.out"
        script_path = f"{log_root}/{run_id}.sh"
        on_cluster(cluster, f'cat > "{script_path}"', stdin=script)
        step = " ".join([
            "srun", f"--jobid={inside}", "--overlap",
            f"--nodes={resources.nodes}", f"--ntasks={resources.nodes}",
            "--ntasks-per-node=1", "--cpus-per-task=1",
            f"--job-name={name}", "--chdir=/tmp", "--propagate=MEMLOCK",
            # --export=NONE leaves the task no PATH to find bash on.
            "--export=NONE", f"--output={log}", f"--error={log}",
            "/bin/bash", script_path,
        ])
        # Detached: srun would otherwise block until the step ends.
        on_cluster(cluster, f"nohup {step} >/dev/null 2>&1 </dev/null &")
        print(f"{name}: step in job {inside}  run_id {run_id}")
        return Job(id=inside, run_id=run_id, log=log, target=target, cluster=cluster)

    log = f"{log_root}/{run_id}_%j.out"
    flags = [
        f"--job-name={name}",
        *resources.sbatch_flags(),
        # The submit dir is node-local to the submit node, so don't start in it.
        "--chdir=/tmp",
        "--propagate=MEMLOCK",
        "--requeue",
        "--open-mode=append",
        # Nothing from this shell belongs in the job: its env points at a home
        # that does not exist on the compute node and holds API tokens, which
        # --export=ALL (sbatch's default) would copy into slurm's job record.
        # The script carries everything it needs.
        "--export=NONE",
        f"--output={log}",
        f"--error={log}",
        # B: the batch script only. The ranks are signalled by it, not by slurm,
        # so preemption and the wall clock look the same to them.
        f"--signal=B:USR1@{cluster.grace_secs}",
    ]
    if after:
        # kill-on-invalid-dep, or a dependency that can never be satisfied
        # leaves this job pending until someone notices it by hand.
        flags += [f"--dependency=afterok:{after}", "--kill-on-invalid-dep=yes"]
    # Flags are shell words: `$HOME` in a path expands on the submit host,
    # where it is that cluster's home.
    out = on_cluster(cluster, "sbatch " + " ".join(flags), stdin=script)
    job_id = out.split()[-1]
    print(f"{name}: job {job_id}  run_id {run_id}")
    return Job(
        id=job_id,
        run_id=run_id,
        log=log.replace("%j", job_id),
        target=target,
        cluster=cluster,
    )


def hold(
    resources: Resources,
    *,
    cluster: Cluster,
    name: str,
    log_root: Path | str,
) -> str:
    """Queue a job that holds ``resources`` and does nothing, and return its id.

    For iterating: one queue wait, then every `submit(..., inside=<id>)` starts
    at once as a step of this allocation instead of queueing behind the
    cluster again. It holds the cards whether or not anything runs in it, so
    cancel it the moment the iteration is over. Its wall clock is
    ``resources.time``; steps die with it.
    """
    log_root = home(log_root)
    log = f"{log_root}/hold_{name}_%j.out"
    flags = [
        f"--job-name=hold-{name}",
        *resources.sbatch_flags(),
        "--chdir=/tmp",
        "--export=NONE",
        f"--output={log}",
        f"--error={log}",
        "--wrap", "'sleep infinity'",
    ]
    on_cluster(cluster, f'mkdir -p "{log_root}"')
    out = on_cluster(cluster, "sbatch " + " ".join(flags))
    job_id = out.split()[-1]
    print(f"hold-{name}: job {job_id}  ({resources.nodes} node(s), {resources.time})")
    return job_id
