"""What a job asks slurm for.

Every field is required: a resource request is a deliberate choice, and a
default here would be an experiment silently making it for you. The presets at
the bottom are this cluster's usable shapes, each carrying the constraint that
forced it.

Validation is structural only -- a cluster's own caps (memory per cpu, cpus per
gpu, gpus per QOS) are policy, and the scheduler reports them better than a
stale copy in here would.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Resources:
    partition: str
    account: str
    qos: str
    time: str
    """Wall clock as slurm spells it, e.g. "7-00:00:00"."""
    gpus: str
    """`<type>:<count>`, e.g. "a100:8", or a bare `<count>` for any type the
    eligible nodes offer -- which is what lets one job shape be scheduled across
    nodes that carry different cards. The count is also the number of ranks: one
    task per GPU, which is what makes DDP work (see roach.slurm.run)."""
    cpus_per_task: int
    """Per rank, not per node -- srun starts one task per GPU."""
    exclusive: bool
    mem: str | None
    """None leaves it to the partition default, which is usually what you want;
    an explicit value is capped by the site's MaxMemPerCPU."""
    constraint: str | None
    nodelist: str | None

    def __post_init__(self) -> None:
        kind, sep, count = self.gpus.rpartition(":")
        if (sep and not kind) or not count.isdigit() or int(count) < 1:
            raise ValueError(
                f"gpus must be '<count>' or '<type>:<count>', got {self.gpus!r}"
            )
        if self.cpus_per_task < 1:
            raise ValueError(f"cpus_per_task must be >= 1, got {self.cpus_per_task}")

    @property
    def ntasks(self) -> int:
        """One rank per GPU."""
        return int(self.gpus.rpartition(":")[2])

    def sbatch_flags(self) -> list[str]:
        flags = [
            f"--partition={self.partition}",
            f"--account={self.account}",
            f"--qos={self.qos}",
            f"--time={self.time}",
            "--nodes=1",
            f"--ntasks-per-node={self.ntasks}",
            f"--gres=gpu:{self.gpus}",
            f"--cpus-per-task={self.cpus_per_task}",
        ]
        if self.exclusive:
            flags.append("--exclusive")
        if self.mem:
            flags.append(f"--mem={self.mem}")
        if self.constraint:
            flags.append(f"--constraint={self.constraint}")
        if self.nodelist:
            flags.append(f"--nodelist={self.nodelist}")
        return flags


# --------------------------------------------------------------------------- #
# This cluster's usable shapes. Each one is a scheduler constraint in disguise;
# the comments are what it cost to find out.
# --------------------------------------------------------------------------- #

AMPERE = Resources(
    partition="il",
    account="infolab",
    qos="il",
    time="7-00:00:00",  # the `il` QOS caps wall clock here; the partition allows 21d under il-lo
    gpus="a100:8",
    cpus_per_task=16,  # 128 cores / 8 ranks
    exclusive=True,  # the mixture is populated into the page cache: take the node's memory
    mem=None,  # --exclusive + DefMemPerGPU gives 2017232M; an explicit --mem is capped lower
    constraint="ampere",
    nodelist=None,
)
"""8xA100 on the fast queue. `il` caps a100 at 10 per user, so one of these at a time."""

AMPERE_LO = Resources(
    partition="il",
    account="infolab",
    qos="il-lo",
    time="21-00:00:00",
    gpus="a100:8",
    cpus_per_task=14,  # the site allows 14 cpus per gpu when not --exclusive
    exclusive=False,  # these nodes carry unrelated cpu-only jobs; demanding the node just queues
    mem=None,
    constraint="ampere",
    nodelist=None,
)
"""The same hardware on the low-priority queue: preemptible, but outside the
10-a100 cap, so it runs alongside an AMPERE job."""

BLACKWELL = Resources(
    partition="il",
    account="infolab",
    qos="il-lo",  # `il` caps b200 at 2 per user, so four is only reachable here
    time="21-00:00:00",
    gpus="b200:4",
    cpus_per_task=36,
    exclusive=False,
    mem="1500000M",  # the node's default for 4 gpus is below what the mixture needs resident
    constraint=None,
    nodelist="blackwell1",
)
"""4xB200. Roughly 3x an 8xA100 job's throughput in the runs measured so far."""
