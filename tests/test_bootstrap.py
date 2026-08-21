"""The batch script's clone protocol, exercised without slurm.

The clone is shared by every job at a commit, which is only safe because of a
lock and a marker. Each test here is one of the ways that goes wrong: two jobs
building at once, a builder preempted mid-build, and a finished job deleting a
clone others are still using.
"""

import os
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from pathlib import Path

import pytest

TOOLS = {
    # `install` is the slow step a second job must not repeat, and it keeps a
    # lock it already has -- which is what makes the seeded lock observable.
    "pixi": """#!/bin/bash
case "$1" in
  install) sleep 1; [[ -f pixi.lock ]] || echo "lock-$(date +%s%N)" > pixi.lock ;;
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
    "python": '#!/bin/bash\necho "ran: python $* job_env=${JOB_ENV_SEEN:-0}"\n',
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

    def job(
        run_id: str,
        sha: str,
        setup: str = "echo built > built.txt",
    ) -> Path:
        filled = script
        for placeholder, value in {
            "@REPO@": str(origin),
            "@COMMIT@": sha,
            "@CLONE_ROOT@": str(tmp_path / "clones"),
            "@LOG_ROOT@": str(tmp_path / "logs"),
            "@SECRETS_DIR@": str(tmp_path / "secrets"),
            "@RUN_ID@": run_id,
            "@NAME@": "t",
            "@TARGET@": "pkg:main",
            "@ARGS@": str(tmp_path / "logs" / "args.json"),
            "@ENV@": f"export PATH={tmp_path / 'bin'}:/usr/bin:/bin",
            "@JOB_ENV@": "export JOB_ENV_SEEN=1",
            "@ROACH@": "test",
            "@SETUP@": setup,
            "@LAUNCH@": (
                "srun --export=ALL pixi run --frozen python"
                " -m roach.slurm.run pkg:main args.json"
            ),
        }.items():
            filled = filled.replace(placeholder, value)
        path = tmp_path / "work" / f"{run_id}.sh"
        path.write_text(filled)
        return path

    def env(job_id: int) -> dict[str, str]:
        return {
            **os.environ,
            "SLURM_JOB_ID": str(job_id),
            "LIVE_JOBS_FILE": str(live),
        }

    def run(path: Path, job_id: int, **kw):
        live.write_text(live.read_text() + f"{job_id}\n")
        out = subprocess.run(
            ["bash", str(path)],
            env=env(job_id),
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
    """Twelve jobs landing together share one clone, one solve and one build."""
    sha = rig.commit()
    scripts = [(rig.job(f"r{i}", sha), 1000 + i) for i in range(12)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        outs = list(pool.map(lambda a: rig.run(*a), scripts))

    assert all(o.returncode == 0 for o in outs), outs[0].stderr
    prepared = [
        line for o in outs for line in o.stdout.splitlines() if "preparing" in line
    ]
    assert sum(f"repo-{sha}" in line for line in prepared) == 1, prepared
    assert all("ran: python" in o.stdout for o in outs)
    # the project's job_env reaches the ranks, not just the batch shell
    assert all("job_env=1" in o.stdout for o in outs)
    # one solve, shared: every run recorded the same lock
    locks = {p.read_text() for p in (rig.root / "logs").glob("*.pixi.lock")}
    assert len(locks) == 1


def test_a_new_commit_inherits_the_previous_solve(rig):
    """Iterating is a commit per attempt, and a clone is per commit, so a solve
    per commit would be a solve per attempt -- minutes each, for commits that
    never touched a dependency. The lock is gitignored, so a new clone seeds it
    from a ready clone with a byte-identical manifest and pixi finds nothing to
    solve."""
    first = rig.commit()
    rig.run(rig.job("first", first), 1001)
    lock = (rig.clones / f"repo-{first}" / "pixi.lock").read_text()

    out = rig.run(rig.job("second", rig.churn()), 1002)  # new commit, same deps
    assert "seeded pixi.lock" in out.stdout, out.stdout
    assert (rig.clones / f"repo-{rig.commit()}" / "pixi.lock").read_text() == lock


def test_a_finished_job_leaves_the_clone_for_the_next_one(rig):
    """A job must not delete its clone on exit: the next job would pay for the
    environment again, and a job still running out of that clone would lose its
    code underneath it."""
    sha = rig.commit()
    rig.run(rig.job("first", sha), 1001)
    clone = rig.clones / f"repo-{sha}"
    assert (clone / ".roach-ready").is_file()

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
    assert clone.is_dir(), "the interrupted build left nothing to recover from"
    assert not (clone / ".roach-ready").exists(), "published a half-built clone"
    assert not (clone / "built.txt").exists()

    out = rig.run(rig.job("after", sha), 1201)
    assert out.returncode == 0, out.stderr
    assert (clone / ".roach-ready").is_file()
    assert (clone / "built.txt").is_file()
