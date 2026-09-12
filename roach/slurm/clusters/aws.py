"""AWS, as a slurm cluster: an AWS ParallelCluster named `roach` in
us-east-1, driven from here over `ssh aws`. The head node is permanent and
tiny; the queues are EC2 fleets that launch a node per job and terminate it
minutes after the job ends, so a queue with no job is free.

Everything the cluster is made of is under `clusters/aws/`: `cluster.yaml`
is the whole definition and `pcluster.sh` creates, updates, deletes and sets
it up. Spend is metered in dollars against the fellowship's credits (see the
roach skill). A submission goes to `H100` (a p5.48xlarge) unless the
instruction names another shape: per dollar it does the most work.
"""

from pathlib import Path

from roach.slurm.clusters import Cluster
from roach.slurm.resources import Resources

AWS = Cluster(
    name="aws",
    site=Path(__file__).with_name("aws.site.sh"),
    grace_secs=120,  # a spot interruption gives two minutes' notice
    submit_host="aws",  # ssh alias to the head node, keys, no gate
)

H100 = Resources(
    partition="h100",
    account=None,  # ParallelCluster runs no accounting
    qos=None,
    time="7-00:00:00",  # the partitions have no limit; a run that checkpoints requeues through it
    gpus="8",
    cpus_per_task=24,  # 192 vCPUs / 8 ranks
    ntasks=None,
    exclusive=True,
    mem=None,
    mem_per_gpu=None,
    constraint=None,
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""A p5.48xlarge: 8 x H100-80G, 192 vCPUs, 2 TB, EFA. On demand, billed by
the second while the node is up (~$55/h). Up to 4 nodes per job."""

H100_SPOT = Resources(
    partition="h100-spot",
    account=None,
    qos=None,
    time="7-00:00:00",
    gpus="8",
    cpus_per_task=24,
    ntasks=None,
    exclusive=True,
    mem=None,
    mem_per_gpu=None,
    constraint=None,
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""The same node as spot: cheaper when there is any, reclaimed with two
minutes' notice, so only for runs that resume."""

A100 = Resources(
    partition="a100",
    account=None,
    qos=None,
    time="7-00:00:00",
    gpus="8",
    cpus_per_task=12,  # 96 vCPUs / 8 ranks
    ntasks=None,
    exclusive=True,
    mem=None,
    mem_per_gpu=None,
    constraint=None,
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""A p4d.24xlarge: 8 x A100-40G, 96 vCPUs, 1.1 TB, EFA. On demand (~$33/h)."""

A100_SPOT = Resources(
    partition="a100-spot",
    account=None,
    qos=None,
    time="7-00:00:00",
    gpus="8",
    cpus_per_task=12,
    ntasks=None,
    exclusive=True,
    mem=None,
    mem_per_gpu=None,
    constraint=None,
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""The p4d as spot."""

H100_1 = Resources(
    partition="h100-1d,h100-1a,h100-1b,h100-1c,h100-1e,h100-1f",  # a queue per AZ; slurm takes the first with a node
    account=None,
    qos=None,
    time="7-00:00:00",
    gpus="1",
    cpus_per_task=16,
    ntasks=None,
    exclusive=True,
    mem=None,
    mem_per_gpu=None,
    constraint=None,
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""A p5.4xlarge: 1 x H100-80G, 16 vCPUs, 256 GB, 100 Gb/s EFA, 3.8 TB NVMe.
What the 64-vCPU P quota allows (four of them); `nodes=4` is four cards over
EFA, not NVLink, and all in one zone. The stopgap until the quota reaches a
p5.48xlarge. FSx is in 1d; a node in another zone reads it across zones."""

A10G = Resources(
    partition="a10g",
    account=None,
    qos=None,
    time="1-00:00:00",
    gpus="1",
    cpus_per_task=8,
    ntasks=None,
    exclusive=True,
    mem=None,
    mem_per_gpu=None,
    constraint=None,
    nodelist=None,
    reservation=None,
    dependency=None,
)
"""A g5.2xlarge: 1 x A10G-24G, 8 vCPUs, 32 GB (~$1.2/h). For probes and
debugging, not for training; one node."""
