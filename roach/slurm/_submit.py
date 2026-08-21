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
    log: Path
    target: str

    @property
    def state(self) -> str:
        out = subprocess.run(
            ["sacct", "-j", self.id, "-n", "--format=State"],
            capture_output=True,
            text=True,
        )
        return out.stdout.split("\n")[0].strip() or "UNKNOWN"


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


def launch(resources: Resources, target: str, args_path: str, pixi_env: str) -> str:
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
    return (
        "srun --export=ALL --chdir=$REPO_DIR --label --kill-on-bad-exit=1 \\\n"
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
    timeout_grace_secs: int | None = None,
    pixi_env: str = "default",
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

    ``timeout_grace_secs`` is how long before the wall clock the ranks are told
    to stop, so the job can checkpoint and requeue itself instead of ending as
    TIMEOUT (see bootstrap.sh). None takes the cluster's preemption grace, so
    the two endings give a run the same time to save; 0 disables it and a job
    that hits its limit then simply stops. It is a request, not a guarantee --
    slurm rounds it to the minute and delivers it around that point -- so leave
    room over what a checkpoint actually costs.
    """
    if timeout_grace_secs is None:
        timeout_grace_secs = cluster.grace_secs
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

    log_root, clone_root = Path(log_root), Path(clone_root)
    log_root.mkdir(parents=True, exist_ok=True)
    args_path = log_root / f"{run_id}.args.json"
    args_path.write_text(json.dumps(args, indent=1, sort_keys=True) + "\n")

    script = files("roach.slurm").joinpath("bootstrap.sh").read_text()
    env_sh = cluster.env.read_text()
    job_env_sh = Path(job_env).read_text() if job_env else ""
    for key, value in {
        "@REPO@": repo,
        "@COMMIT@": commit,
        "@RUN_ID@": run_id,
        "@NAME@": name,
        "@TARGET@": target,
        "@ROACH@": roach.__version__,
        "@ARGS@": str(args_path),
        "@LOG_ROOT@": str(log_root),
        "@CLONE_ROOT@": str(clone_root),
        "@SECRETS_DIR@": str(secrets_dir),
        "@SETUP@": "\n".join(setup),
        "@ENV@": env_sh,
        "@JOB_ENV@": job_env_sh,
        "@LAUNCH@": launch(resources, target, str(args_path), pixi_env),
        "@REQUEUE_ON_TIMEOUT@": "1" if timeout_grace_secs else "0",
    }.items():
        script = script.replace(key, value)

    log = log_root / f"{run_id}_%j.out"
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
    ]
    if timeout_grace_secs:
        # B: the batch script only. The ranks are signalled by it, not by slurm,
        # so preemption and the wall clock look the same to them.
        flags.append(f"--signal=B:USR1@{timeout_grace_secs}")
    if after:
        # kill-on-invalid-dep, or a dependency that can never be satisfied
        # leaves this job pending until someone notices it by hand.
        flags += [f"--dependency=afterok:{after}", "--kill-on-invalid-dep=yes"]
    # Slurm env vars outrank command-line flags when submitting from inside an
    # allocation, which would silently impose that job's shape on this one.
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("SLURM_", "SBATCH_"))
    }
    out = subprocess.run(
        ["sbatch", *flags],
        input=script,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    job_id = out.stdout.split()[-1]
    print(f"{name}: job {job_id}  run_id {run_id}")
    return Job(
        id=job_id,
        run_id=run_id,
        log=Path(str(log).replace("%j", job_id)),
        target=target,
    )
