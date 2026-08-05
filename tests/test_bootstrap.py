"""The batch script's clone protocol, exercised without slurm.

The clone is shared by every job at a commit, which is only safe because of a
lock, a marker and a rename. Each test here is one of the ways that goes wrong:
two jobs building at once, a builder preempted mid-build, a finished job
deleting a clone others are still using, and a reaper deleting a live one.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from pathlib import Path

import pytest

TOOLS = {
    # `pixi install` is the slow step a second job must not repeat.
    "pixi": """#!/bin/bash
case "$1" in
  install) sleep 1; echo "lock-$(date +%s%N)" > pixi.lock ;;
  run) shift; while [[ $1 == --* ]]; do shift; done; exec "$@" ;;
esac
""",
    "srun": '#!/bin/bash\nwhile [[ $1 == --* ]]; do shift; done\nexec "$@"\n',
    # every id the tests use is live unless the test says otherwise
    "squeue": """#!/bin/bash
for a in "$@"; do
  if [[ $a == -j ]]; then
    shift; [[ -f $LIVE_JOBS_FILE ]] && grep -qx "$2" "$LIVE_JOBS_FILE" && echo "$2"
    exit 0
  fi
done
[[ -f $LIVE_JOBS_FILE ]] && cat "$LIVE_JOBS_FILE"
exit 0
""",
    "python": '#!/bin/bash\necho "ran: python $*"\n',
}


@pytest.fixture
def rig(tmp_path: Path):
    """A throwaway origin, fake tools, and a filled-in copy of bootstrap.sh."""
    for name in ("origin", "clones", "logs", "bin", "secrets", "work"):
        (tmp_path / name).mkdir()
    for name, body in TOOLS.items():
        p = tmp_path / "bin" / name
        p.write_text(body)
        p.chmod(0o755)
    (tmp_path / "secrets" / "github").write_text("token\n")
    live = tmp_path / "live-jobs"
    live.write_text("")

    origin = tmp_path / "origin"
    git = ["git", "-C", str(origin)]
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    (origin / ".gitignore").write_text("pixi.lock\n")
    (origin / "pyproject.toml").write_text('[project]\nname="fake"\n')
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run(
        [*git, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        check=True,
    )

    script = files("roach.slurm").joinpath("bootstrap.sh").read_text()

    def commit() -> str:
        out = subprocess.run(
            [*git, "rev-parse", "HEAD"], capture_output=True, text=True
        )
        return out.stdout.strip()

    def churn() -> str:
        (origin / "churn.txt").write_text(str(time.time_ns()))
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run(
            [*git, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c"],
            check=True,
        )
        return commit()

    def job(run_id: str, sha: str, setup: str = "echo built > built.txt") -> Path:
        filled = script
        for key, value in {
            "@REPO@": str(origin),
            "@ROACH_REPO@": str(origin),
            "@COMMIT@": sha,
            "@ROACH_COMMIT@": sha,
            "@CLONE_ROOT@": str(tmp_path / "clones"),
            "@LOG_ROOT@": str(tmp_path / "logs"),
            "@SECRETS_DIR@": str(tmp_path / "secrets"),
            "@RUN_ID@": run_id,
            "@NAME@": "t",
            "@TARGET@": "pkg:main",
            "@ARGS@": str(tmp_path / "logs" / "args.json"),
            "@ENV@": f"export PATH={tmp_path / 'bin'}:/usr/bin:/bin",
            "@SETUP@": setup,
        }.items():
            filled = filled.replace(key, value)
        path = tmp_path / "work" / f"{run_id}.sh"
        path.write_text(filled)
        return path

    def env(job_id: int, ttl: int = 99) -> dict[str, str]:
        return {
            **os.environ,
            "SLURM_JOB_ID": str(job_id),
            "ROACH_CLONE_TTL_DAYS": str(ttl),
            "LIVE_JOBS_FILE": str(live),
        }

    def run(path: Path, job_id: int, ttl: int = 99, **kw):
        live.write_text(live.read_text() + f"{job_id}\n")
        out = subprocess.run(
            ["bash", str(path)],
            env=env(job_id, ttl),
            capture_output=True,
            text=True,
            **kw,
        )
        live.write_text(
            "".join(
                line
                for line in live.read_text().splitlines(True)
                if line.strip() != str(job_id)
            )
        )
        return out

    rig = type("Rig", (), {})()
    rig.root, rig.clones, rig.live = tmp_path, tmp_path / "clones", live
    rig.commit, rig.churn, rig.job, rig.run, rig.env = commit, churn, job, run, env
    return rig


def test_concurrent_jobs_at_one_commit_build_the_clone_once(rig):
    """Twelve jobs landing together used to be twelve clones, twelve solves and
    twelve builds of the same commit."""
    sha = rig.commit()
    scripts = [(rig.job(f"r{i}", sha), 1000 + i) for i in range(12)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        outs = list(pool.map(lambda a: rig.run(*a), scripts))

    assert all(o.returncode == 0 for o in outs), outs[0].stderr
    # the project clone and roach's are separate dirs; each is built once
    prepared = [
        line for o in outs for line in o.stdout.splitlines() if "preparing" in line
    ]
    assert sum(f"repo-{sha}" in line for line in prepared) == 1, prepared
    assert sum(f"roach-{sha}" in line for line in prepared) == 1, prepared
    assert all("ran: python" in o.stdout for o in outs)
    # one solve, shared: every run recorded the same lock
    locks = {p.read_text() for p in (rig.root / "logs").glob("*.pixi.lock")}
    assert len(locks) == 1


def test_a_finished_job_leaves_the_clone_for_the_next_one(rig):
    """The old script deleted its clone on exit, which is what made every job
    pay for the environment again -- and would now delete it under a job that is
    still running."""
    sha = rig.commit()
    rig.run(rig.job("first", sha), 1001)
    clone = rig.clones / f"repo-{sha}"
    assert (clone / ".roach-ready").is_file()
    assert not list((clone / ".roach-inuse").iterdir())  # claim released

    out = rig.run(rig.job("second", sha), 1002)
    assert "preparing" not in out.stdout


def test_a_killed_builder_leaves_a_recoverable_clone(rig):
    """Preemption during the build must not publish a half-built clone, and must
    not wedge the next job behind a lock or a stale directory."""
    sha = rig.churn()
    path = rig.job("killed", sha, setup="sleep 30")
    rig.live.write_text(rig.live.read_text() + "1200\n")
    proc = subprocess.Popen(
        ["bash", str(path)],
        env=rig.env(1200),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()

    clone = rig.clones / f"repo-{sha}"
    assert not (clone / ".roach-ready").exists()
    assert Path(f"{clone}.partial").is_dir()

    out = rig.run(rig.job("after", sha), 1201)
    assert out.returncode == 0, out.stderr
    assert (clone / ".roach-ready").is_file()
    assert not Path(f"{clone}.partial").exists()
    assert (clone / "built.txt").is_file()


def test_the_reaper_keeps_a_clone_a_live_job_still_holds(rig):
    """Sweeping by age alone would delete the clone out from under a long job
    that has held it since before the cutoff."""
    old = rig.commit()
    rig.run(rig.job("old", old), 1001)
    clone = rig.clones / f"repo-{old}"
    (clone / ".roach-used").touch()
    os.utime(clone / ".roach-used", (0, 0))  # ancient
    (clone / ".roach-inuse" / "1300").touch()  # a job that is still running
    rig.live.write_text("1300\n")

    rig.run(rig.job("new", rig.churn()), 1002, ttl=0)
    assert clone.is_dir(), "reaped a clone a live job was using"

    # and once that job is gone, the next sweep retires it
    rig.live.write_text("")
    rig.run(rig.job("newer", rig.churn()), 1003, ttl=0)
    assert not clone.exists()
