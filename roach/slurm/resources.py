"""What a job asks slurm for.

Every field is required: a resource request is a deliberate choice, and a
default here would be an experiment silently making it for you. Each cluster
module under `roach.slurm.clusters` carries presets for its usable shapes.

Validation is structural only -- a cluster's own caps (memory per cpu, cpus per
gpu, gpus per QOS) are policy, and the scheduler reports them better than a
stale copy in here would.
"""

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
    task per GPU, which is what makes DDP work (see roach.slurm.run).

    `"0"` asks for no GPU at all, and runs a single rank. A cpu-only stage of a
    pipeline that wants no accelerator should not have to hold one: GPUs are the
    scarcest thing on a node, and a job that keeps one idle is capping how many
    of its siblings can run."""
    cpus_per_task: int
    """Per rank, not per node -- srun starts one task per GPU by default."""
    ntasks: int | None
    """Ranks to start. None means one per GPU, which is what DDP wants and what
    roach.slurm.run assumes. Set it to 1 to give a single process several GPUs:
    a stage that parallelises inside one process (sentence-transformers spawning
    a worker per device, say) wants all of them visible to one rank, not one
    rank each."""
    exclusive: bool
    mem: str | None
    """None leaves it to the partition default, which is usually what you want;
    an explicit value is capped by the site's MaxMemPerCPU."""
    mem_per_gpu: str | None
    """Memory per GPU, as an alternative to `mem`.

    Needed wherever a partition sets DefMemPerGPU: that default is applied when
    working out whether a job fits, and `--mem` does not displace it, so the
    most GPUs a job can hold is RealMemory / DefMemPerGPU however little memory
    it actually wants -- a job that wants a whole node's cards may not be able
    to ask for them with `mem` at all. `--mem-per-gpu` replaces the default and
    lifts it."""
    constraint: str | None
    nodelist: str | None
    dependency: str | None
    """An sbatch dependency, e.g. ``afterok:12345``. The job stays pending
    until it is satisfied, and slurm cancels it if it never can be."""
    reservation: str | None
    """A reservation to run inside, by name (`scontrol show res`). A reserved
    node is taken out of general scheduling, so its cards are reachable only
    with this set -- and a job that sets it is confined to them."""
    exclude: str | None = None
    """Nodes to keep off, by name or slurm hostlist (`node[4,7]`). The
    scheduler treats a node with a full local disk as healthy, so a job placed
    there starts and then wedges; this is how a known-bad node is kept out of
    the running without pinning the job to one specific good node."""
    nodes: int = 1
    """How many nodes to hold. `gpus`, `cpus_per_task` and `ntasks` are all
    per-node, so this multiplies the job: 4 nodes of "a100:8" is 32 ranks. DDP
    spans them without any extra configuration -- every rank is a slurm task and
    roach.slurm.run reads its identity from srun (see `set_torch_dist_env`)."""

    def __post_init__(self) -> None:
        kind, sep, count = self.gpus.rpartition(":")
        if (sep and not kind) or not count.isdigit():
            raise ValueError(
                f"gpus must be '<count>' or '<type>:<count>', got {self.gpus!r}"
            )
        if sep and int(count) == 0:
            raise ValueError(f"no GPUs is '0', not a type with none: {self.gpus!r}")
        if self.cpus_per_task < 1:
            raise ValueError(f"cpus_per_task must be >= 1, got {self.cpus_per_task}")
        if self.ntasks is not None and self.ntasks < 1:
            raise ValueError(f"ntasks must be >= 1 or None, got {self.ntasks}")
        if self.nodes < 1:
            raise ValueError(f"nodes must be >= 1, got {self.nodes}")
        if self.mem and self.mem_per_gpu:
            raise ValueError("give mem or mem_per_gpu, not both")

    @property
    def ranks_per_node(self) -> int:
        """Tasks per node: `ntasks` if given, else one per GPU."""
        if self.ntasks is not None:
            return self.ntasks
        return max(1, int(self.gpus.rpartition(":")[2]))

    @property
    def ranks(self) -> int:
        """How many tasks srun starts in total, across every node."""
        return self.nodes * self.ranks_per_node

    def sbatch_flags(self) -> list[str]:
        flags = [
            f"--partition={self.partition}",
            f"--account={self.account}",
            f"--qos={self.qos}",
            f"--time={self.time}",
            f"--nodes={self.nodes}",
            f"--ntasks-per-node={self.ranks_per_node}",
            f"--cpus-per-task={self.cpus_per_task}",
        ]
        if self.gpus != "0":
            flags.append(f"--gres=gpu:{self.gpus}")
        if self.exclusive:
            flags.append("--exclusive")
        if self.mem:
            flags.append(f"--mem={self.mem}")
        if self.mem_per_gpu:
            flags.append(f"--mem-per-gpu={self.mem_per_gpu}")
        if self.constraint:
            flags.append(f"--constraint={self.constraint}")
        if self.nodelist:
            flags.append(f"--nodelist={self.nodelist}")
        if self.exclude:
            flags.append(f"--exclude={self.exclude}")
        if self.reservation:
            flags.append(f"--reservation={self.reservation}")
        if self.dependency:
            flags.append(f"--dependency={self.dependency}")
        return flags
