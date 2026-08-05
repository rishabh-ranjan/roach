"""roach.slurm: the parts that are pure functions, and so are the parts that bit us.

Every check here corresponds to a failure that cost real time on the cluster:
arguments that do not match the target, a resource shape that slurm rejects, and
a batch script that has lost a placeholder.
"""

from __future__ import annotations

import importlib.metadata
import inspect
import json

import pytest

from roach.slurm import Resources, check_args, resolve, timestamp
from roach.slurm._submit import installed_source
from roach.slurm._submit import submit as submit_fn


def sample(a: int, b: str, c: list[int], run_id: str) -> None:  # noqa: ARG001
    pass


def test_resolve_requires_module_attr():
    assert resolve("roach.slurm._submit:timestamp") is timestamp
    with pytest.raises(ValueError):
        resolve("roach.slurm._submit")


def test_timestamp_has_no_characters_that_break_wandb_or_cargo():
    t = timestamp()
    assert ":" not in t and "/" not in t


def test_check_args_accepts_a_matching_call():
    check_args(f"{__name__}:sample", {"a": 1, "b": "x", "c": [1, 2], "run_id": "r"})


@pytest.mark.parametrize(
    "args, message",
    [
        ({"a": 1, "b": "x", "c": [1], "run_id": "r", "d": 0}, "no argument"),
        ({"a": 1, "b": "x"}, "missing argument"),
        ({"a": "not an int", "b": "x", "c": [1], "run_id": "r"}, "a="),
        ({"a": 1, "b": "x", "c": ["not an int"], "run_id": "r"}, "c="),
    ],
)
def test_check_args_rejects(args, message):
    with pytest.raises(TypeError, match=message):
        check_args(f"{__name__}:sample", args)


def ampere(**over) -> Resources:
    kwargs = dict(
        partition="il",
        account="infolab",
        qos="il",
        time="7-00:00:00",
        gpus="a100:8",
        cpus_per_task=16,
        exclusive=True,
        mem=None,
        constraint="ampere",
        nodelist=None,
    )
    return Resources(**{**kwargs, **over})


def test_one_task_per_gpu():
    assert ampere().ntasks == 8
    assert ampere(gpus="b200:4").ntasks == 4


def test_sbatch_flags():
    flags = ampere().sbatch_flags()
    assert "--ntasks-per-node=8" in flags
    assert "--gres=gpu:a100:8" in flags
    assert "--cpus-per-task=16" in flags
    assert "--exclusive" in flags
    assert not any(f.startswith("--mem") for f in flags)
    assert "--mem=1500000M" in ampere(mem="1500000M").sbatch_flags()


@pytest.mark.parametrize(
    "bad", [{"gpus": "a100"}, {"gpus": "a100:0"}, {"cpus_per_task": 0}]
)
def test_resources_rejects_nonsense(bad):
    with pytest.raises(ValueError):
        ampere(**bad)


def test_a_git_install_reports_the_commit_it_was_built_from(monkeypatch):
    """The job clones the roach that submitted it, so a queued run cannot change
    because roach moved; that pin comes from PEP 610 metadata."""

    class Dist:
        @staticmethod
        def read_text(_name):
            return json.dumps(
                {
                    "url": "https://github.com/rishabh-ranjan/roach",
                    "vcs_info": {"vcs": "git", "commit_id": "a" * 40},
                }
            )

    # patched on the stdlib module: submit.py resolves it at call time, and
    # `roach.slurm._submit` is the *function* (the package re-exports it), so
    # there is no module attribute to patch instead.
    monkeypatch.setattr(importlib.metadata, "distribution", lambda _: Dist)
    assert installed_source("roach") == (
        "https://github.com/rishabh-ranjan/roach",
        "a" * 40,
    )


def test_an_install_with_no_git_provenance_is_an_error(monkeypatch):
    class Dist:
        @staticmethod
        def read_text(_name):
            return None  # a plain wheel: nothing says where it came from

    monkeypatch.setattr(importlib.metadata, "distribution", lambda _: Dist)
    with pytest.raises(RuntimeError, match="which roach commit"):
        installed_source("roach")


def test_every_placeholder_in_the_script_is_one_submit_fills():
    """A placeholder nobody fills reaches the compute node as a literal @NAME@,
    and fails there rather than here."""
    import re
    from importlib.resources import files

    script = files("roach.slurm").joinpath("bootstrap.sh").read_text()
    filled = set(re.findall(r'"(@[A-Z_]+@)"', inspect.getsource(submit_fn)))
    assert set(re.findall(r"@[A-Z_]+@", script)) == filled


def test_job_env_is_not_inherited():
    """--export=ALL is sbatch's default and would copy this shell's home, PATH
    and API tokens into the job (and slurm's job record); the batch script
    carries everything it needs."""
    assert '"--export=NONE"' in inspect.getsource(submit_fn)


def test_bootstrap_lets_srun_inherit_the_job_environment():
    """--export=NONE (which keeps the submit shell out of the job) also stops
    srun from passing the job's own environment to its tasks, so `pixi` is not
    on their PATH; SLURM_EXPORT_ENV=ALL puts it back."""
    from importlib.resources import files

    script = files("roach.slurm").joinpath("bootstrap.sh").read_text()
    assert "srun --export=ALL" in script


def test_presets_are_one_rank_per_gpu():
    """The preset's cpus_per_task is per rank, so a preset that quietly asked
    for a node's worth of cores per rank would be rejected at submit."""
    from roach.slurm import AMPERE, AMPERE_LO, BLACKWELL

    for preset in (AMPERE, AMPERE_LO, BLACKWELL):
        assert preset.ntasks == int(preset.gpus.rpartition(":")[2])
        assert preset.ntasks * preset.cpus_per_task <= 288  # the widest node here
