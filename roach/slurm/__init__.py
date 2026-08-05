"""Run python functions on slurm: one function, one job, one rank per GPU.

    from roach.slurm import AMPERE, submit

    submit("mypkg.train:main", args={...}, resources=AMPERE, name="run",
           repo_root=..., log_root=..., clone_root=..., secrets_dir=...,
           clone_ttl_days=7,
           setup=("pixi run build-sampler",))

The job clones the commit you submitted from, builds its environment on the
node, and calls the target in every rank. Preemption is handled by the target
saving a resumable checkpoint; slurm requeues, and the same run id resumes it.

Project-agnostic: what to build inside the clone is the `setup` argument, and
where things live are arguments too. What is *not* agnostic, deliberately, is
env.sh and the presets -- those describe this cluster and this user.
"""

# _submit rather than submit: a module and the function it exports cannot share
# a name, or the re-export below shadows the module and `import roach.slurm.submit`
# quietly hands you the function instead.
from roach.slurm.resources import AMPERE, AMPERE_LO, BLACKWELL, Resources
from roach.slurm._submit import Job, check_args, submit, timestamp
from roach.slurm.target import resolve

__all__ = [
    "AMPERE",
    "AMPERE_LO",
    "BLACKWELL",
    "Job",
    "Resources",
    "check_args",
    "resolve",
    "submit",
    "timestamp",
]
