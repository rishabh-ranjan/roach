# Roach Examples

This directory contains comprehensive examples demonstrating all capabilities of the roach experiment management framework.

## Overview

The roach framework provides three main components:

1. **Store System** - Save/load PyTorch tensors and log metrics
2. **Queue System** - Task execution with preconditions and dependencies
3. **Plotting Utilities** - Publication-quality figure generation

## Examples

### 1. ML Workflow (`ml_workflow.py`)

Demonstrates the Store system with a simulated machine learning workflow.

**Features demonstrated:**
- Store initialization with parent directories and custom IDs
- Saving PyTorch tensors (model weights, embeddings)
- Logging metrics over time (loss, accuracy)
- Loading saved objects and metrics
- Working with subdirectories in the store
- Iterating over multiple stores
- Using the global `store` instance and `scratch` namespace

**Run it:**
```bash
python examples/ml_workflow.py
```

**What it does:**
- Runs three mock training experiments (baseline, extended, long_run)
- Saves model checkpoints, configs, and embeddings
- Logs training metrics (loss, accuracy)
- Analyzes and compares all experiments
- Demonstrates global store usage

**Output:**
- Creates temporary directory with multiple store subdirectories
- Each store contains `.pt` files (PyTorch objects) and `.bin` files (logged metrics)
- Prints comprehensive analysis of all experiments

### 2. Queue Demo (`queue_demo.py`)

Demonstrates the queue-based task execution system with workers.

**Features demonstrated:**
- Basic task submission with `submit(queue_dir, cmd, chk)`
- Task preconditions and dependencies
- Task chaining (A → B → C)
- Parallel independent tasks
- Multiline bash commands
- Python tasks via heredoc
- Integration with Store
- Error handling and failure recovery

**Run it (submission only):**
```bash
python examples/queue_demo.py
```

**Run it (with worker):**
```bash
python examples/queue_demo.py --run-worker
```

**What it does:**
- Submits ~25 diverse tasks to a temporary queue
- Demonstrates 8 different usage patterns
- Shows task dependencies and preconditions
- Prints instructions for running workers

**Queue directory structure:**
```
queue_dir/
├── queued/      # Tasks waiting to run
├── .checking/   # Tasks having preconditions checked
├── active/      # Currently running tasks
├── done/        # Successfully completed tasks
├── failed/      # Failed tasks
└── paused/      # Manually paused tasks
```

**Worker commands:**
```bash
# Run all tasks then exit
python -m roach.worker <queue_dir>

# Run one task then exit
python -m roach.worker <queue_dir> --one-task

# Keep running (for continuous job processing)
python -m roach.worker <queue_dir> --persist
```

**Task file format:**
```
<precondition command>
---
<main command>
===
<worker output gets appended here>
```

### 3. Plotting Demo (`plotting_demo.py`)

Demonstrates publication-quality plotting utilities.

**Features demonstrated:**
- `setup_plt()` for paper-ready plot configuration
- `save_fig()` for saving figures as PDFs
- `save_tex()` for generating LaTeX tables
- Using the `LINE` constant for proper figure sizing
- Training curve visualization
- Multi-experiment comparison plots
- Error bars and confidence intervals
- Various subplot layouts
- Loading data from Store and plotting

**Run it:**
```bash
python examples/plotting_demo.py
```

**What it does:**
- Generates 6 different plot types
- Creates publication-ready figures (PDF format)
- Generates LaTeX table of results
- Demonstrates proper sizing for academic papers

**Output files:**
- `basic_training_curve.pdf`
- `multi_experiment_comparison.pdf`
- `advanced_error_bars.pdf`
- `store_data_plot.pdf`
- `subplot_layouts.pdf`
- `results_table.tex`

## Running All Examples

To run all examples and verify the framework works correctly:

```bash
bash examples/run_all.sh
```

This script:
1. Runs the ML workflow demo
2. Runs the plotting demo
3. Submits queue tasks and processes them with a worker
4. Verifies all outputs were created successfully
5. Prints a summary

## Common Usage Patterns

### Pattern 1: Single Experiment with Store

```python
from roach.store import store, scratch
import torch

# Initialize store
store.init(parent="./experiments", store_id="my_experiment")

# Use scratch for temporary state
scratch.epoch = 0
scratch.best_loss = float('inf')

# Training loop
for epoch in range(100):
    # ... training code ...

    # Log metrics
    store.log("loss", loss_value)
    store.log("accuracy", acc_value)

    # Save checkpoint
    if loss_value < scratch.best_loss:
        store.save(model.state_dict(), "best_model")
        scratch.best_loss = loss_value

    scratch.epoch += 1
```

### Pattern 2: Task Dependencies

```python
from roach.submit import submit

# Task A
chk_a = submit(queue_dir, "python train_model.py")

# Task B depends on A
chk_b = submit(queue_dir, "python evaluate_model.py", chk=chk_a)

# Task C depends on B
chk_c = submit(queue_dir, "python generate_plots.py", chk=chk_b)
```

### Pattern 3: Hyperparameter Sweep

```python
from roach.submit import submit

queue_dir = "./sweep_queue"
learning_rates = [0.001, 0.01, 0.1]

for lr in learning_rates:
    cmd = f"python train.py --lr {lr} --store_id sweep_lr_{lr}"
    submit(queue_dir, cmd)

# Run multiple workers in parallel
# Each worker will pick up a different task
```

### Pattern 4: Publication Plots

```python
from roach.paper import setup_plt, save_fig, LINE
from matplotlib import pyplot as plt

setup_plt()

fig, ax = plt.subplots(figsize=(LINE, LINE * 0.6))
ax.plot(x, y)
ax.set_xlabel("Epoch")
ax.set_ylabel("Loss")

save_fig(fig, "figures/training_curve.pdf")
```

## Best Practices

### Store
- Use descriptive store IDs (e.g., `exp_baseline_lr0.001`)
- Organize related data in subdirectories (e.g., `results/metrics`, `checkpoints/best`)
- Use `store.ls("pattern*")` to find specific keys
- Always check `store.store_dir` is set before saving

### Queue
- Use preconditions for task dependencies
- Keep commands simple or use Python scripts
- Monitor queue directories to track progress
- Failed tasks remain in `failed/` for debugging

### Plotting
- Always call `setup_plt()` first
- Use `LINE` constant for consistent figure widths
- Save as PDF for publication quality
- Use descriptive filenames

## Advanced Features

### Pause/Resume Tasks

```bash
# Pause a running task
mv queue_dir/active/task_id queue_dir/paused/

# Resume a paused task
mv queue_dir/paused/task_id queue_dir/active/
```

The worker will automatically send SIGSTOP/SIGCONT to the process tree.

### Multiple Workers

Run multiple workers in parallel (e.g., on different GPUs):

```bash
# Terminal 1 (GPU 0)
CUDA_VISIBLE_DEVICES=0 python -m roach.worker queue_dir --persist

# Terminal 2 (GPU 1)
CUDA_VISIBLE_DEVICES=1 python -m roach.worker queue_dir --persist
```

Workers include GPU info in their IDs for tracking.

### Analyzing Stores Programmatically

```python
from roach.store import iter_stores
import pandas as pd

results = []
for store_id, s in iter_stores("./experiments"):
    config = s.load("config")
    losses = s.load("loss")

    results.append({
        "experiment": store_id,
        "lr": config["learning_rate"],
        "final_loss": losses[-1].item(),
    })

df = pd.DataFrame(results)
print(df.sort_values("final_loss"))
```

## Troubleshooting

### Store issues
- **"key already exists"**: Set `allow_overwrite=True` in `store.save()`
- **"no files found for key"**: Check store directory with `store.ls()`
- **"multiple files found"**: Don't save same key with different extensions

### Queue issues
- **Tasks stuck in queued**: Check precondition with manual test
- **Worker exits immediately**: Normal behavior if queue is empty (use `--persist`)
- **Tasks fail silently**: Check task file in `failed/` directory for error output

### Plotting issues
- **Figures too small**: Use `LINE` constant for width
- **Missing plots**: Ensure `setup_plt()` is called first
- **Text too large**: Adjust `font_scale` in `setup_plt()`

## Additional Resources

- Main README: `../README.md`
- Source code: `../roach/`
- CLAUDE.md: `../CLAUDE.md` (architecture notes)

## Questions?

Check the source code in `roach/` for implementation details. The codebase is intentionally minimal and readable.
