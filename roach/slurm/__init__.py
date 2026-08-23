"""Run python functions on slurm: one function, one job, one rank per GPU.

    from roach.slurm import submit
    from roach.slurm.clusters.ilc import AMPERE, ILC

    submit("mypkg.train:main", args={...}, resources=AMPERE, cluster=ILC,
           name="run", repo_root=..., log_root=..., clone_root=..., secrets_dir=...)

The job clones the commit you submitted from, builds its environment on the
node, and calls the target in every rank. Preemption is handled by the target
saving a resumable checkpoint; slurm requeues, and the same run id resumes it.

Project-agnostic: what to build inside the clone is the `setup` argument, the
project's job environment is `job_env`, and where things live are arguments
too. Cluster-specific code lives under `roach.slurm.clusters`, one module per
supported cluster.
"""

# _submit rather than submit: a module and the function it exports cannot share
# a name, or the re-export below shadows the module and `import roach.slurm.submit`
# quietly hands you the function instead.
from roach.slurm._submit import Job, check_args, hold, submit, timestamp
from roach.slurm.clusters import Cluster
from roach.slurm.resources import Resources
from roach.slurm.target import resolve

__all__ = [
    "Cluster",
    "Job",
    "Resources",
    "check_args",
    "hold",
    "resolve",
    "submit",
    "timestamp",
]
