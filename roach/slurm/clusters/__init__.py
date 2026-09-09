"""What roach knows about a particular slurm cluster.

Everything in `roach.slurm` outside this package is any-slurm: the clone
protocol, the launcher, the requeue-on-timeout dance. What differs between
clusters -- where the home and the shared store are, where slurm lives, how long
preemption gives a job to save -- is a `Cluster`, and each supported cluster is
a module here that defines one plus the `Resources` shapes that are usable on
it. Submit with `cluster=<module>.<NAME>`.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cluster:
    name: str
    site: Path
    """Declarations only, sourced ahead of `roach/slurm/node.sh` on every node
    the job holds: `site_detect`, `NODE_HOME`, `SCRATCH`, `SLURM_BIN` (and an exported `SLURM_CONF` where the batch environment lacks one),
    `TMPROOT`, `IN_SCRATCH` and `site_job_env`. node.sh is what
    acts on them, the same way everywhere; a site file that computes anything
    is a cluster leaking into the core."""
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
    ControlMaster for a Duo-gated host), and slurm must be on PATH in a
    non-interactive shell there -- that is the host's dotfiles' business."""
