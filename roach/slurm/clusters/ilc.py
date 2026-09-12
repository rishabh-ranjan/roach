"""The ILC cluster: partition `il`, qos `il-interactive` / `il` / `il-lo`.

The presets are this cluster's usable shapes. Each one is a scheduler
constraint in disguise; the comments are what it cost to find out.
"""

from pathlib import Path

from roach.slurm.clusters import Cluster
from roach.slurm.resources import Resources

ILC = Cluster(
    name="ilc",
    site=Path(__file__).with_name("ilc.site.sh"),
    grace_secs=300,  # the preemption GraceTime on every qos
    submit_host=None,  # sessions run on an ILC node; the login host has no ~/scratch
)

AMPERE = Resources(
    partition="il",
    account="infolab",
    qos="il",
    time="7-00:00:00",  # the `il` QOS caps wall clock here; the partition allows 21d under il-lo
    gpus="a100:8",
    cpus_per_task=16,  # 128 cores / 8 ranks
    ntasks=None,
    exclusive=True,  # take the node's memory: a job that populates the page cache wants all of it
    mem=None,  # --exclusive + DefMemPerGPU gives 2017232M; an explicit --mem is capped lower
    mem_per_gpu=None,
    constraint="ampere",
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""8xA100 on the fast queue. `il` caps a100 at 10 per user, so one of these at a time."""

AMPERE_LO = Resources(
    partition="il",
    account="infolab",
    qos="il-lo",
    time="21-00:00:00",
    gpus="a100:8",
    cpus_per_task=16,  # 128 cores / 8 ranks
    ntasks=None,
    exclusive=True,  # since 2026-09 the il partition is gpu-only, so nothing else shares the node
    mem=None,
    mem_per_gpu=None,
    constraint="ampere",
    nodelist=None,
    reservation=None,
    dependency=None,
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
    ntasks=None,
    exclusive=False,
    mem="1500000M",  # the node's default for 4 gpus is well below the node's memory
    mem_per_gpu=None,
    constraint=None,
    nodelist="blackwell1",
    reservation=None,
    dependency=None,
)
"""4xB200, the only node that has them."""
