"""Marlowe (Stanford's DGX H100 SuperPOD): partitions `preempt` / `batch`,
qos `normal` / `medium`, accounts `marlowe-m000137` / `marlowe-m000137-pm06`.

Every node is the same: 8 x H100-80G, 112 cores, 1950000M. The presets are
the two ways a job gets there; which to spend is the human's instruction,
never a default (see the roach skill).
"""

from pathlib import Path

from roach.slurm.clusters import Cluster
from roach.slurm.resources import Resources

MARLOWE = Cluster(
    name="marlowe",
    site=Path(__file__).with_name("marlowe.site.sh"),
    grace_secs=900,  # GraceTime on the preempt partition
    submit_host="marlowe",  # ssh alias; Duo-gated, so a ControlMaster must be up
)

H100 = Resources(
    partition="batch",
    account="marlowe-m000137-pm06",  # the metered allocation: GPU-hours, shared by the group
    qos="medium",
    time="2-00:00:00",  # the partition's MaxTime; a run that checkpoints requeues through it
    gpus="8",
    cpus_per_task=14,  # 112 cores / 8 ranks
    ntasks=None,
    exclusive=True,
    mem=None,  # --exclusive + DefMemPerCPU=13000M gives 1456000M of the node's 1950000M
    mem_per_gpu=None,
    constraint=None,
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""A whole H100 node on `batch`: not preemptible, billed to the allocation.
Up to 16 nodes per job (`nodes=`)."""

H100_PREEMPT = Resources(
    partition="preempt",
    account="marlowe-m000137",  # the base account: free, preempt-only
    qos="normal",
    time="12:00:00",  # the partition's MaxTime
    gpus="8",
    cpus_per_task=14,
    ntasks=None,
    exclusive=True,
    mem=None,
    mem_per_gpu=None,
    constraint=None,
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""The same node on `preempt`: unmetered, requeued with 15 minutes' notice
whenever a `batch` or `hero` job wants it -- at any point, including after
the run has finished its work -- so only for runs that resume."""
