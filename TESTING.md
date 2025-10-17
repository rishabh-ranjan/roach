# Roach Testing with Pixi

This document describes how the roach examples have been tested using pixi for environment management.

## Environment Setup

A pixi environment has been created with all necessary dependencies:

- **Python**: 3.11 (required for strictfire compatibility)
- **PyTorch**: 2.8.0
- **Matplotlib**: 3.10.7
- **Seaborn**: 0.13.2
- **Pandas**: 2.3.3
- **Psutil**: 7.1.0
- **Strictfire**: 0.4.0 (required for queue worker CLI)

## Configuration Files

### pixi.toml

The `pixi.toml` file defines the environment and provides convenient task runners:

```toml
[project]
name = "roach"
version = "0.0.1"
description = "Experiment management framework for ML and data science"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
python = "3.11.*"
pytorch = ">=2.0"
matplotlib = ">=3.5"
seaborn = ">=0.12"
pandas = ">=1.5"
psutil = ">=5.9"
pip = ">=23.0"

[tasks]
install-roach = "pip install -e ."
test-ml-workflow = "python examples/ml_workflow.py"
test-queue-demo = "python examples/queue_demo.py"
test-plotting-demo = "python examples/plotting_demo.py"
test-all = "bash examples/run_all.sh"
```

### pyproject.toml

The `pyproject.toml` has been updated to include `strictfire` as a dependency:

```toml
dependencies = [
    "matplotlib",
    "pandas",
    "seaborn",
    "torch",
    "psutil",
    "strictfire",  # Added for CLI support
]
```

## Installation

```bash
# Install pixi environment and dependencies
pixi install

# Install roach in editable mode
pixi run install-roach
```

## Running Examples

### Using Pixi Tasks

```bash
# Run individual examples
pixi run test-ml-workflow
pixi run test-plotting-demo
pixi run test-queue-demo

# Run comprehensive test suite
pixi run test-all
```

### Direct Execution

```bash
# Run examples directly in pixi environment
pixi run python examples/ml_workflow.py
pixi run python examples/plotting_demo.py
pixi run python examples/queue_demo.py

# Run queue demo with worker
pixi run python examples/queue_demo.py --run-worker

# Run worker manually
pixi run python -m roach.worker <queue_dir>

# Submit tasks to queue
pixi run python -m roach.submit <queue_dir> --cmd "echo 'Hello'"
```

## Test Results

All three examples have been successfully tested in the pixi environment:

### 1. ML Workflow Example ✓

**Tested Features:**
- Store initialization with multiple experiments
- Saving PyTorch tensors (.pt files)
- Logging metrics over time (.bin files)
- Loading saved objects
- Iterating over multiple stores
- Global store instance usage
- Scratch namespace for temporary state

**Output:**
- Created 3 experiment stores (baseline, extended, long_run)
- Each with 5-15 epochs of training data
- Successfully saved and loaded models, configs, and metrics
- Demonstrated proper metric aggregation and comparison

**Sample Output:**
```
exp_baseline:
  Epochs trained: 5
  Final loss: 0.4632
  Final accuracy: 0.8823

exp_extended:
  Epochs trained: 10
  Final loss: 0.2139
  Final accuracy: 0.9100

exp_long_run:
  Epochs trained: 15
  Final loss: 0.2078
  Final accuracy: 0.9766
```

### 2. Plotting Demo Example ✓

**Tested Features:**
- Publication-quality plot setup with seaborn
- Multiple plot types (line, error bars, subplots)
- LaTeX table generation
- Loading data from Store and plotting
- Proper figure sizing for papers (LINE constant)
- PDF output format

**Output Files Generated:**
- `basic_training_curve.pdf`
- `multi_experiment_comparison.pdf`
- `advanced_error_bars.pdf`
- `store_data_plot.pdf`
- `subplot_layouts.pdf`
- `results_table.tex`

**Sample LaTeX Output:**
```latex
\begin{table}[h]
\centering
\caption{Experimental Results}
\label{tab:results}
\begin{tabular}{lccccc}
\hline
Experiment & LR & Epochs & Final Loss & Final Acc & Best Acc \\
\hline
baseline & 0.001 & 50 & 0.0910 & 1.0269 & 1.0978 \\
high_lr & 0.01 & 50 & 0.0868 & 0.9505 & 1.0410 \\
long_train & 0.001 & 100 & -0.0258 & 0.9268 & 1.0908 \\
\hline
\end{tabular}
\end{table}
```

### 3. Queue Demo Example ✓

**Tested Features:**
- Task submission with preconditions
- Task dependencies and chaining
- Multiple task types (bash, multiline, Python)
- Queue directory structure (queued, active, done, failed)
- Worker lifecycle management
- Integration with Store system
- Error handling

**Tasks Submitted:**
- 3 basic tasks
- 3 chained dependent tasks (A → B → C)
- 1 task with failing precondition
- 5 parallel independent tasks
- 1 multiline bash script
- 2 Python tasks
- 1 Store integration task
- 3 error handling tasks

**Total:** 19 tasks across 8 different patterns

### Comprehensive Test Suite

The `run_all.sh` script includes:

1. Installation verification
2. ML workflow execution test
3. Plotting demo with output verification
4. Queue task submission
5. Worker execution (one task)
6. Worker execution (all tasks)
7. Store iteration test
8. Task dependency chain test

All tests can be run with:
```bash
pixi run test-all
```

## Known Issues & Workarounds

### Python 3.13 Compatibility

**Issue:** The `strictfire` library (v0.4.1) uses the deprecated `pipes` module, which was removed in Python 3.13.

**Workaround:** Use Python 3.11 in the pixi environment:
```toml
python = "3.11.*"
```

### Long-running Workers

**Issue:** Workers with persist mode or tasks with failing preconditions can run indefinitely.

**Workaround:** Use timeouts or run without `--persist` flag for testing.

## Performance Notes

- ML workflow: ~5-10 seconds
- Plotting demo: ~3-5 seconds
- Queue demo: ~2 seconds (submission only)
- Queue demo with worker: ~20-30 seconds (executes all tasks)
- Full test suite: ~2-3 minutes

## File Structure

```
roach/
├── pixi.toml                 # Pixi environment configuration
├── pixi.lock                 # Locked dependencies
├── .pixi/                    # Pixi environment directory
│   └── envs/default/         # Python 3.11 environment
├── pyproject.toml            # Updated with strictfire
├── examples/
│   ├── ml_workflow.py        ✓ Tested
│   ├── plotting_demo.py      ✓ Tested
│   ├── queue_demo.py         ✓ Tested
│   ├── README.md             # Example documentation
│   └── run_all.sh            ✓ Tested
└── roach/
    ├── store.py
    ├── submit.py
    ├── worker.py
    └── paper.py
```

## Verification Commands

Quick verification that everything works:

```bash
# Check installation
pixi run python -c "import roach; print('✓ roach works')"

# Check all dependencies
pixi run python << 'EOF'
import roach
import torch
import matplotlib
import seaborn
import psutil
import strictfire
print("✓ All dependencies available")
EOF

# Run all examples
pixi run test-ml-workflow > /dev/null && echo "✓ ML workflow"
pixi run test-plotting-demo > /dev/null && echo "✓ Plotting demo"
pixi run test-queue-demo > /dev/null && echo "✓ Queue demo"
```

## Next Steps

To continue testing or development:

1. **Activate the environment:**
   ```bash
   pixi shell
   ```

2. **Run examples interactively:**
   ```bash
   python examples/ml_workflow.py
   ```

3. **Develop new features:**
   ```bash
   # Edit source files
   vim roach/store.py

   # Test immediately (installed in editable mode)
   python examples/ml_workflow.py
   ```

4. **Add new tests:**
   ```bash
   # Add to pixi.toml
   [tasks]
   test-new-feature = "python examples/new_feature.py"

   # Run it
   pixi run test-new-feature
   ```

## Conclusion

All roach examples have been successfully tested in a clean pixi environment. The framework is working correctly with all dependencies properly installed and configured.

**Test Status: ✓ ALL PASSED**

- ML Workflow: ✓
- Plotting Demo: ✓
- Queue Demo: ✓
- Environment Setup: ✓
- Dependency Management: ✓
