# roach.slurm

Run a python function on slurm. You write the function and say what hardware it
needs; roach handles the rest.

```python
from roach.slurm import BLACKWELL, submit

submit(
    "mypkg.train:main",            # module:attr -- checked at submit time
    args={"lr": 1e-3, "steps": 1000},
    resources=BLACKWELL,           # or Resources(...) for another shape
    name="lr-1e-3",
    setup=("pixi run build-sampler",),   # built inside the clone, if you need it
    repo_root=..., log_root=..., clone_root=..., secrets_dir=...,
)
```

A sweep is a python loop around that call. There is no config format, no CLI and
no DSL: the arguments are a dict, and the loop that builds them is the record of
the experiment.

## What a job actually does

1. **Refuses to submit** a dirty or unpushed tree, and records the commit.
2. **Checks `args` against the target's signature** (names *and* types, via
   beartype). A typo fails in a second instead of forty minutes into a job.
3. Writes `args` as JSON next to the run's logs, mints a `run_id`, and hands
   slurm a generated script -- on stdin, so nothing needs shared storage.
4. In the job: clones **that commit** into node-local scratch, brings the node
   up (`env.sh`: node-local `HOME`, caches, tokens, first-login setup), reuses
   the run's pinned `pixi.lock`, runs your `setup` commands.
5. `srun` starts **one rank per GPU**; `roach.slurm.run` maps
   `SLURM_PROCID`/`LOCALID`/`NTASKS` to `RANK`/`LOCAL_RANK`/`WORLD_SIZE`, so
   `torch.distributed` comes up with no launcher.

## Preemption

Because each rank is a slurm *task*, slurm's SIGTERM reaches all of them
directly. The contract is:

* your function handles SIGTERM and writes a resumable checkpoint (atomically:
  temp file, fsync, rename);
* the batch script ignores the signal and waits, so slurm does not tear the step
  down mid-save;
* slurm requeues the job, and because `run_id` is fixed, the next attempt
  resumes from that checkpoint.

Pass `run_id=` to relaunch an existing run by hand -- same wandb run, same
output directory, same checkpoint.

## Resources

`Resources` has no defaults: a resource request is a deliberate choice. The
presets (`AMPERE`, `AMPERE_LO`, `BLACKWELL`) are this cluster's usable shapes,
and each carries the scheduler constraint that forced it -- QOS GPU caps, the
cpus-per-gpu limit for non-exclusive jobs, why an explicit `--mem` gets you
*less* memory than none at all.

## What is not portable

`env.sh` and the presets describe this cluster and this user. Everything else --
what to build (`setup`), where things live (`*_root`), what to run (`target`) --
is an argument.

## Consuming it

Depend on roach by pinned commit, so a run cannot change because roach moved:

```toml
roach = { git = "https://github.com/rishabh-ranjan/roach", rev = "<commit>" }
```

The base install is slurm-only (`beartype`); the deprecated frameworks live in
extras (`roach[queues]`, `roach[stores]`, `roach[paper]`, `roach[all]`).
