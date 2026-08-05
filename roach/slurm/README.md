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
    clone_ttl_days=7,
)
```

A sweep is a python loop around that call. There is no config format, no CLI and
no DSL: the arguments are a dict, and the loop that builds them is the record of
the experiment.

Nor is anything read from the environment. Every knob the job uses is an
argument to `submit()`, so the same call is the same job on any node, and a
value nobody passed is an error at submit time rather than whatever the node
happened to export.

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

* **The first job at a commit builds it; the rest take a lock.** `.roach-ready`,
  written last, is what publishes the clone; a builder that is preempted drops
  the lock and leaves an unmarked directory for the next job to wipe. The build
  happens in place, never staged and renamed: an environment is keyed to the
  path it was installed at, so moving the project afterwards makes pixi
  reinstall the editable path dependency — for a maturin project, a full
  recompile, run by every rank at once into the one shared environment.
* **`pixi.lock` is solved once per commit** and lives in the clone (it is
  gitignored, so a fresh checkout has none). A copy lands next to the run's logs
  as a record of what the run used. Ranks start under `pixi run --frozen`: in a
  shared clone, a rank that re-solved would rewrite the lock underneath every
  other job at that commit.
* **Nothing is deleted when a job ends.** A clone is retired once no live job
  holds it and nothing has touched it for `clone_ttl_days`, swept by
  whichever job publishes the next clone.

Put `clone_root` on the node's own big disk, on the same filesystem as the
package caches — pixi hardlinks the environment from them when it can, and
copies ~8 GiB when it cannot.

### The clone is read-only

**Your job must not write inside its own checkout.** This is the one thing the
shared clone asks of an experiment, and roach cannot enforce it — a job that
breaks the rule fails as corrupted output or a race, not as an error.

It used to be safe: each job had a private clone that was deleted at exit, so an
experiment could scribble in its working directory and nobody noticed. Now every
job at that commit on that node is in the same directory at the same time. Two
runs writing `outputs/`, a checkpoint saved next to the code, a scratch file
named after the dataset rather than the run — all of these are now two processes
writing one path.

The rule in practice:

* **Write under `log_root`, or an output root you pass as an argument.** Both are
  arguments to the target, so two runs get two paths by construction.
* **Read anything in the checkout; treat it as `chmod -R a-w`.** Code, task
  lists, config files committed to the repo: all fine to read.
* **Do not `os.chdir` and use relative paths.** The job starts in the clone, so a
  relative output path lands in it.
* **`setup` is the exception**, and only the exception. It runs once, under the
  lock, before the clone is published — building compiled extensions there is
  exactly what it is for.

If an experiment genuinely needs a writable copy of the tree, copy it to
somewhere under `run_id` and work there.

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
