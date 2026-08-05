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
4. In the job: brings the node up (`env.sh`: node-local `HOME`, caches, tokens,
   first-login setup), then takes the node's clone of **that commit** —
   building it, `pixi install` and your `setup` commands and all, if it is the
   first job at that commit on that node.
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

## Clones

`clone_root` holds **one clone per commit per node**, shared by every job at
that commit. It used to be one per job, thrown away at exit, and that cost far
more than the disk: pixi keys an environment on the project path (a detached
environment is literally `NAME-HASH_OF_PATH`), uv keys built wheels on the mtime
of `pyproject.toml`, and cargo's artifacts live under the manifest. A clone at a
fresh `mktemp` path therefore missed every one of those caches by construction,
so each job re-solved the environment and recompiled the extensions — minutes of
a full allocation, per job, to reproduce what the last job had already built.

Reproducibility is unchanged: a clone is still exactly the submitted commit, and
a different commit is a different directory, so a queued job cannot change under
you. What changes:

* **The first job at a commit builds it; the rest take a lock.** The builder
  works in `<dir>.partial` and publishes with a rename, so the clone is either
  absent or complete. A builder that is preempted drops the lock and leaves only
  the `.partial`, which the next job wipes.
* **The clone is read-only once it is ready.** Jobs at one commit share it, so an
  experiment that writes into its own checkout now has its jobs stepping on each
  other. Write to `log_root`, or to a path of your own.
* **`pixi.lock` is solved once per commit** and lives in the clone (it is
  gitignored, so a fresh checkout has none). A copy lands next to the run's logs
  as a record of what the run used. Ranks start under `pixi run --frozen`: in a
  shared clone, a rank that re-solved would rewrite the lock underneath every
  other job at that commit.
* **Nothing is deleted when a job ends.** A clone is retired once no live job
  holds it and nothing has touched it for `ROACH_CLONE_TTL_DAYS` (default 7),
  swept by whichever job publishes the next clone.

Put `clone_root` on the node's own big disk, on the same filesystem as the
package caches — pixi hardlinks the environment from them when it can, and
copies ~8 GiB when it cannot.

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

## Tests

`pixi run test`. They cover the pure functions -- target resolution, the
argument check, resource shapes, the placeholders the script and `submit()` must
agree on, and the two environment flags that mean opposite things at their two
layers (`--export=NONE` keeps the submitting shell out of the job;
`srun --export=ALL` lets the job's own environment reach its tasks). Each one is
a mistake that cost real time on a cluster.

## Consuming it

Depend on roach by pinned commit, so a run cannot change because roach moved:

```toml
roach = { git = "https://github.com/rishabh-ranjan/roach", rev = "<commit>" }
```

The base install is slurm-only (`beartype`); the deprecated frameworks live in
extras (`roach[queues]`, `roach[stores]`, `roach[paper]`, `roach[all]`).
