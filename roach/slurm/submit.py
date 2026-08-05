"""Submit a python function to slurm.

The submitting side owns everything that needs the repo: it refuses a dirty or
unpushed tree, records the commit, checks the arguments against the target's
signature, and hands slurm a script that reproduces the run from that commit.
Nothing here is site-specific -- paths, account and QOS are arguments.
"""

from __future__ import annotations

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


def preflight() -> tuple[str, str]:
    """(repo url, commit) of a clean, pushed tree -- the job clones that."""
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
    return repo, commit


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def submit(
    target: str,
    args: dict[str, Any],
    resources: Resources,
    *,
    name: str,
    repo_root: Path | str,
    log_root: Path | str,
    clone_root: Path | str,
    secrets_dir: Path | str,
    setup: tuple[str, ...] = (),
    run_id: str | None = None,
    dry_run: bool = False,
) -> Job:
    """Run ``target(**args)`` on ``resources``, one rank per GPU.

    ``run_id`` is minted here and injected into ``args`` if the target declares
    it; pass one to relaunch an existing run, which is how a run resumes from a
    checkpoint it wrote earlier.
    """
    os.chdir(repo_root)
    # The job runs from the repo root, so targets are importable relative to it
    # (examples.foo:main). Match that here, or the submit-time check would fail
    # on targets the job can import perfectly well.
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    repo, commit = preflight()
    run_id = run_id or timestamp()
    if "run_id" in inspect.signature(resolve(target)).parameters:
        args = {**args, "run_id": run_id}
    check_args(target, args)

    log_root, clone_root = Path(log_root), Path(clone_root)
    log_root.mkdir(parents=True, exist_ok=True)
    args_path = log_root / f"{run_id}.args.json"
    args_path.write_text(json.dumps(args, indent=1, sort_keys=True) + "\n")

    script = files("roach.slurm").joinpath("bootstrap.sh").read_text()
    for key, value in {
        "@REPO@": repo,
        "@COMMIT@": commit,
        "@RUN_ID@": run_id,
        "@NAME@": name,
        "@TARGET@": target,
        "@ARGS@": str(args_path),
        "@LOG_ROOT@": str(log_root),
        "@CLONE_ROOT@": str(clone_root),
        "@SECRETS_DIR@": str(secrets_dir),
        "@SETUP@": "\n".join(setup),
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
    if dry_run:
        print("DRY RUN: sbatch", " ".join(flags))
        return Job(id="dry-run", run_id=run_id, log=Path(str(log)), target=target)

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
