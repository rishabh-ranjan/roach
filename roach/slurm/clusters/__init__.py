"""What roach knows about a particular slurm cluster.

Everything in `roach.slurm` outside this package is any-slurm: the clone
protocol, the launcher, the requeue-on-timeout dance. What differs between
clusters -- how a node is brought up, where scratch and secrets live, how long
preemption gives a job to save -- is a `Cluster`, and each supported cluster is
a module here that defines one plus the `Resources` shapes that are usable on
it. Submit with `cluster=<module>.<NAME>`.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cluster:
    name: str
    env: Path
    """Shell sourced in the batch script before anything else, on every node the
    job holds: node-local HOME, scratch, caches, package manager, tokens. Must
    not read configuration from the environment (see the tests) and must fail
    loudly on a node it cannot bring up."""
    grace_secs: int
    """Seconds between preemption's SIGTERM and the kill; the default for
    `submit(timeout_grace_secs=)` so the wall clock gives a run the same time
    to checkpoint that preemption does."""
