# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`roach` is an experiment management framework for machine learning and data science workflows. It provides:
- A queue-based task execution system with preconditions
- A store for saving/loading PyTorch tensors and logging metrics
- Plotting utilities for generating publication-quality figures

Named after cockroaches for their hardiness - experiments should survive and persist through various challenges.

## Installation & Setup

```bash
# Install from git
pip install git+https://github.com/rishabh-ranjan/roach

# Install in development mode (from repo root)
pip install -e .
```

This project uses `flit` as the build backend (configured in `pyproject.toml`).

## Architecture

### Queue System (`queue.py` + `worker.py`)

The queue system manages task execution with preconditions:

**Queue Structure**: Tasks are organized in directories:
- `queued/` - Tasks waiting to be executed
- `.checking/` - Tasks being checked for preconditions
- `active/` - Currently running tasks
- `paused/` - Tasks that have been paused
- `done/` - Successfully completed tasks
- `failed/` - Failed tasks

**Task Format**: Each task file contains:
```
<precondition command>
---
<main command>
===
<worker output gets appended here>
```

**Key Classes/Functions**:
- `Queue.submit(cmd, chk="true")` - Submit a task with optional precondition check
- `worker(queue_dir, persist=False, one_task=False)` - Main worker loop that processes tasks
- Workers poll the queue directory every `SLEEP_TIME` (1 second)
- Workers can be paused/resumed by moving task files between `active/` and `paused/`
- Workers handle SIGTERM by re-queueing tasks

**Worker Lifecycle**:
1. Worker acquires task from `queued/` → `.checking/`
2. Runs precondition check; if fails, re-queues
3. If passes, moves to `active/` and runs main command
4. On completion, moves to `done/` or `failed/` based on exit code
5. Worker exits if queue is empty (unless `persist=True`)

### Store System (`store.py`)

The store manages experiment artifacts:

**Key Classes**:
- `Store(store_dir=None)` - Main storage interface
- `store.init(parent=None, store_id=None)` - Initialize a new store
- `store.save(obj, key, allow_overwrite=False)` - Save PyTorch objects as `.pt` files
- `store.log(key, val)` - Append float values to `.bin` files (for metrics over time)
- `store.load(key)` - Load objects (automatically detects `.pt` or `.bin` format)
- `store.ls(pattern="*")` - List stored keys matching pattern
- `iter_stores(parent)` - Iterate over all stores in a parent directory

**Global Instances**:
- `store` - Global Store instance for the current experiment
- `scratch` - SimpleNamespace for temporary experiment state

**Binary Format**: `.bin` files store floats as packed 4-byte values (struct format `'f'`)

### Plotting (`plot.py`)

Publication-quality figure generation:

- `setup_plt()` - Configure seaborn/matplotlib with paper-ready defaults
- `save_fig(fig, save_key)` - Save figures to `figures/{save_key}.pdf`
- `save_tex(tex, save_key)` - Save LaTeX tables to `tables/{save_key}.tex`
- `LINE = 5.5` - Constant for figure width (likely in inches)

## Running Tasks

```bash
# Submit a task to queue
python -m roach.queue <queue_dir> --cmd "<command>" --chk "<precondition>"

# Start a worker (exits when queue is empty)
python -m roach.worker <queue_dir>

# Start a persistent worker (keeps running)
python -m roach.worker <queue_dir> --persist

# Run one task and exit
python -m roach.worker <queue_dir> --one-task
```

Both `queue.py` and `worker.py` use `strictfire` for CLI argument parsing.

## Process Management

- `kill_proc_tree(pid, ...)` - Kill entire process tree (from psutil docs)
- Workers kill child processes with SIGKILL when interrupted
- Pausing: Workers detect when task files are moved to `paused/` and send SIGSTOP to process tree
- Resuming: When moved back to `active/`, workers send SIGCONT

## Key Behaviors

- Worker IDs include timestamp, hostname, PID, and `CUDA_VISIBLE_DEVICES` for GPU tracking
- Task IDs use timestamp + nanoseconds for uniqueness
- Workers don't log - inspect state directly from queue directory structure
- Workers handle race conditions via atomic file operations (rename)
- Store directory structure is printed on init: "roach store_dir is {path}"
