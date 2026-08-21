# roach.slurm

Run a python function on slurm. You write the function and say what hardware it
needs; roach handles the rest.

```python
from roach.slurm import submit
from roach.slurm.clusters.ilc import BLACKWELL, ILC

submit(
    "mypkg.train:main",            # module:attr -- checked at submit time
    args={"lr": 1e-3, "steps": 1000},
    resources=BLACKWELL,           # or Resources(...) for another shape
    cluster=ILC,                   # which cluster's node setup and presets
    name="lr-1e-3",
    job_env="expts/job_env.sh",    # the project's own per-job shell, or None
    setup=(),                      # extra build/fetch commands, run in the clone
    pixi_env="default",            # pixi environment the ranks run under; an
                                   # env pixi does not build by default needs a
                                   # `pixi install -e <env>` in `setup`
    repo_root=..., log_root=..., clone_root=..., secrets_dir=...,
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
4. In the job: brings the node up (the cluster's env: node-local `HOME`,
   caches, tokens, first-login setup), sources the project's `job_env`, then
   takes the node's clone of **that commit** —
   building it, `pixi install` and your `setup` commands and all, if it is the
   first job at that commit on that node.
5. `srun` starts **one rank per GPU**; `roach.slurm.run` maps
   `SLURM_PROCID`/`LOCALID`/`NTASKS` to `RANK`/`LOCAL_RANK`/`WORLD_SIZE`, so
   `torch.distributed` comes up with no launcher.

## Preemption and the wall clock

Both end the same way, and neither needs you. Because each rank is a slurm
*task*, SIGTERM reaches all of them directly. The contract is:

* your function handles SIGTERM and writes a resumable checkpoint (atomically:
  temp file, fsync, rename);
* the batch script ignores the signal and waits, so slurm does not tear the step
  down mid-save;
* slurm requeues the job, and because `run_id` is fixed, the next attempt
  resumes from that checkpoint.

Slurm does that requeue for preemption and node failure only: **`TIMEOUT` is a
normal ending and no setting makes it a requeue.** So the batch script asks for
`--signal=B:USR1@<timeout_grace_secs>` (the cluster's preemption grace by
default), and on that signal it
sends its own steps the same SIGTERM slurm would have, waits for them, and calls
`scontrol requeue` itself. A run therefore survives its wall clock exactly as it
survives preemption -- the ranks cannot tell the two apart -- and long runs stop
needing a person to notice and resubmit them.

Requeued once, never twice: the signal is delivered once, it is acted on only
while the ranks are still running, and preemption never reaches that code
because it arrives as SIGTERM, which the batch script ignores. Set
`timeout_grace_secs=0` to opt out; raise it if a checkpoint takes longer than
the grace to write.

Pass `run_id=` to relaunch an existing run by hand -- same wandb run, same
output directory, same checkpoint.

## Clones

`clone_root` holds **one clone per commit per node**, shared by every job at
that commit. The path is what makes that worth doing: pixi keys an environment
on the project path (a detached environment is literally `NAME-HASH_OF_PATH`),
uv keys built wheels on the mtime of `pyproject.toml`, and cargo's artifacts live
under the manifest — so a per-job clone at a fresh path misses every one of those
caches and re-solves and recompiles what the last job already built.

A clone is exactly the submitted commit, and a different commit is a different
directory, so a queued job cannot change under you. What sharing implies:

* **The first job at a commit builds it; the rest take a lock.** `.roach-ready`,
  written last, is what publishes the clone; a builder that is preempted drops
  the lock and leaves an unmarked directory for the next job to wipe. The build
  happens in place, never staged and renamed: an environment is keyed to the
  path it was installed at, so moving the project afterwards makes pixi
  reinstall the editable path dependency — for a maturin project, a full
  recompile, run by every rank at once into the one shared environment.
* **`pixi.lock` is solved once, not once per commit.** It is gitignored, so a
  fresh clone has none and pixi would solve from scratch — the same solve, for
  every commit that never touched a dependency. A new clone copies the lock from
  a ready clone whose `pyproject.toml` is byte-identical; pixi validates it
  against the manifest anyway and re-solves if it disagrees, so a stale one
  costs nothing (measured: ~60s of preparation, against ~9 minutes without it).
  A copy lands next to the run's logs as a record of what the run used. Ranks start under
  `pixi run --frozen`: in a shared clone, a rank that re-solved would rewrite
  the lock underneath every other job at that commit.
* **What is left is `pixi install`, ~50s per new commit**, materializing an
  8.5 GiB environment. Pixi keys an environment on the project path, so a
  per-commit clone means a per-commit environment; when the environment already
  exists at that path the same command takes 0.05s. Hardlinking one from a
  matching clone does not work — pixi rebuilds a prefix it did not
  create. Avoiding it would need the manifest to sit at a path that does not
  change per commit.
* **Nothing is ever deleted.** No job removes a clone, at exit or otherwise,
  and there is no TTL. A clone that nobody wants sits there costing very little
  (see below), and a job that deleted directories on a timer would eventually
  delete one somebody was using.

Put `clone_root` on the node's own big disk, on the same filesystem as the
package caches — pixi reflinks the environment from them when it can, and copies
~8 GiB when it cannot.

### Reclaiming the space

**If a node's disk fills up, delete clones by hand:**

```bash
rm -rf <clone_root>/repo-*        # e.g. /lfs/local/0/roach_clones/repo-*
```

Nothing else has to happen: the next job at a key re-clones and rebuilds it. Do
not do this while jobs are running from a clone — check with
`squeue -u $USER` first, since a clone is the running job's code and
environment.

They are cheaper than `du` suggests. Each environment reports ~8 GiB but is
reflinked from the package cache, so its own cost is ~230 MiB (measured with
`btrfs filesystem du -s`: 8.17 GiB total, 222 MiB exclusive) -- thirty-odd
environments on a node measured ~7 GiB of real disk. Treat a full disk as a real
event to act on, not something to pre-empt with a policy.

### The clone is read-only

**Your job must not write inside its own checkout.** This is the one thing the
shared clone asks of an experiment, and roach cannot enforce it — a job that
breaks the rule fails as corrupted output or a race, not as an error.

Every job at that commit on that node is in the same directory at the same time.
Two runs writing `outputs/`, a checkpoint saved next to the code, a scratch file
named after the dataset rather than the run — each of these is two processes
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

`Resources` has no defaults: a resource request is a deliberate choice. Each
cluster module ships presets for its usable shapes, and each preset carries the
scheduler constraint that forced it -- QOS GPU caps, the cpus-per-gpu limit for
non-exclusive jobs, why an explicit `--mem` gets you *less* memory than none at
all.

## Clusters

`roach.slurm.clusters.<name>` is everything roach knows about one cluster: a
`Cluster` (the shell that brings a node up, the preemption grace) and the
`Resources` presets that are usable there. Everything outside that package is
any-slurm. Supported:

| module | cluster |
| --- | --- |
| `roach.slurm.clusters.ilc` | ILC: partition `il`, qos `il-interactive` / `il` / `il-lo` |

A project's own environment -- a build cache, a limit its runs need -- is not
the cluster's business: pass it as `job_env`, a shell file sourced after the
cluster's on every node.

## Tests

`pixi run test`. They cover the pure functions -- target resolution, the
argument check, resource shapes, the placeholders the script and `submit()` must
agree on, and the two environment flags that mean opposite things at their two
layers (`--export=NONE` keeps the submitting shell out of the job;
`srun --export=ALL` lets the job's own environment reach its tasks) -- and the
clone protocol, run against fake `pixi`/`srun` without slurm.

## Versions

A job runs `bootstrap.sh` from the roach that *submitted* it and
`roach.slurm.run` from the roach in the *clone's* environment. Pin roach in the
project's manifest and keep the submitting environment at the same pin; the job
header prints both commit and roach version.
