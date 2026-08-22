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
    """Seconds between preemption's SIGTERM and the kill. The wall clock
    signals the batch script this long before the limit (`--signal=B:USR1@`),
    so both endings give a run the same time to checkpoint. Slurm rounds it to
    the minute, so leave room over what a checkpoint actually costs."""
    submit_host: str | None
    """ssh destination of a host where this cluster's slurm commands run, or
    None when they run where `submit()` is called. With a host, everything
    that touches the cluster at submit time -- the args file, `sbatch`,
    `sacct` -- goes over `ssh -o BatchMode=yes`, so the session never has to
    be on that cluster; the repo, the preflight and the argument check stay
    local. The connection must already be passwordless (keys, or a live
    ControlMaster for a Duo-gated host)."""
    submit_shell: str
    """Shell prefix run before every command on `submit_host`; what makes
    slurm callable in a non-login ssh shell there (a PATH, a SLURM_CONF).
    Empty when nothing is needed."""
