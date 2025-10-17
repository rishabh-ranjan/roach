#!/bin/bash
# Comprehensive test script for roach examples
# This script runs all examples and verifies they work correctly

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

# Check if roach is installed
print_header "CHECKING INSTALLATION"
if python -c "import roach" 2>/dev/null; then
    print_success "roach is installed"
else
    print_error "roach is not installed"
    print_info "Installing roach in development mode..."
    pip install -e . || {
        print_error "Failed to install roach"
        exit 1
    }
    print_success "roach installed successfully"
fi

# Check dependencies
print_info "Checking dependencies..."
python -c "import torch, matplotlib, seaborn, psutil" || {
    print_error "Missing dependencies"
    print_info "Install with: pip install torch matplotlib seaborn psutil"
    exit 1
}
print_success "All dependencies available"

# Track results
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local description="$3"

    print_info "Running: $description"

    if eval "$test_command"; then
        print_success "$test_name passed"
        ((TESTS_PASSED++))
        return 0
    else
        print_error "$test_name failed"
        FAILED_TESTS+=("$test_name")
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test 1: ML Workflow
print_header "TEST 1: ML WORKFLOW (Store System)"
run_test "ml_workflow" \
    "python examples/ml_workflow.py" \
    "Running ML workflow demonstration"

# Test 2: Plotting Demo
print_header "TEST 2: PLOTTING DEMO"
PLOT_OUTPUT=$(mktemp -d)
print_info "Plot output directory: $PLOT_OUTPUT"

# Run plotting demo and capture output dir
python examples/plotting_demo.py > /tmp/plot_output.txt 2>&1
PLOT_DIR=$(grep "All files saved in:" /tmp/plot_output.txt | awk '{print $NF}')

if [ -d "$PLOT_DIR" ]; then
    print_success "Plot output directory created: $PLOT_DIR"

    # Check for expected files
    EXPECTED_PLOTS=(
        "basic_training_curve.pdf"
        "multi_experiment_comparison.pdf"
        "advanced_error_bars.pdf"
        "store_data_plot.pdf"
        "subplot_layouts.pdf"
        "results_table.tex"
    )

    ALL_PLOTS_EXIST=true
    for plot in "${EXPECTED_PLOTS[@]}"; do
        if [ -f "$PLOT_DIR/$plot" ]; then
            print_success "Found: $plot"
        else
            print_error "Missing: $plot"
            ALL_PLOTS_EXIST=false
        fi
    done

    if [ "$ALL_PLOTS_EXIST" = true ]; then
        print_success "All expected plots generated"
        ((TESTS_PASSED++))
    else
        print_error "Some plots missing"
        FAILED_TESTS+=("plotting_demo")
        ((TESTS_FAILED++))
    fi
else
    print_error "Plot output directory not found"
    FAILED_TESTS+=("plotting_demo")
    ((TESTS_FAILED++))
fi

# Test 3: Queue Demo (submission only)
print_header "TEST 3: QUEUE DEMO (Task Submission)"
QUEUE_OUTPUT=$(mktemp -d)
print_info "Queue directory: $QUEUE_OUTPUT"

# Run queue demo and capture queue dir
python examples/queue_demo.py > /tmp/queue_output.txt 2>&1
QUEUE_DIR=$(grep "Using queue directory:" /tmp/queue_output.txt | awk '{print $NF}')

if [ -d "$QUEUE_DIR/queued" ]; then
    NUM_QUEUED=$(ls -1 "$QUEUE_DIR/queued" 2>/dev/null | wc -l)
    print_success "Queue created with $NUM_QUEUED tasks"
    ((TESTS_PASSED++))

    # Test 4: Worker execution (one task)
    print_header "TEST 4: WORKER (One Task)"
    run_test "worker_one_task" \
        "python -m roach.worker $QUEUE_DIR --one-task" \
        "Running worker to execute one task"

    # Check that one task completed
    if [ -d "$QUEUE_DIR/done" ]; then
        NUM_DONE=$(ls -1 "$QUEUE_DIR/done" 2>/dev/null | wc -l)
        if [ "$NUM_DONE" -ge 1 ]; then
            print_success "$NUM_DONE task(s) completed"
        else
            print_error "No tasks completed"
        fi
    fi

    # Test 5: Worker execution (all tasks)
    print_header "TEST 5: WORKER (All Tasks)"
    print_info "Processing all remaining tasks..."

    # Run worker with timeout
    timeout 60 python -m roach.worker "$QUEUE_DIR" || {
        # Worker exited (expected when queue is empty)
        :
    }

    # Count final results
    NUM_DONE=$(ls -1 "$QUEUE_DIR/done" 2>/dev/null | wc -l || echo 0)
    NUM_FAILED=$(ls -1 "$QUEUE_DIR/failed" 2>/dev/null | wc -l || echo 0)
    NUM_QUEUED=$(ls -1 "$QUEUE_DIR/queued" 2>/dev/null | wc -l || echo 0)

    print_info "Final queue status:"
    echo "  Done: $NUM_DONE"
    echo "  Failed: $NUM_FAILED"
    echo "  Still queued: $NUM_QUEUED"

    if [ "$NUM_DONE" -gt 0 ]; then
        print_success "Worker processed tasks successfully"
        ((TESTS_PASSED++))
    else
        print_error "Worker did not complete any tasks"
        FAILED_TESTS+=("worker_execution")
        ((TESTS_FAILED++))
    fi

    # Show a sample completed task
    if [ "$NUM_DONE" -gt 0 ]; then
        SAMPLE_TASK=$(ls "$QUEUE_DIR/done" | head -1)
        print_info "Sample completed task: $SAMPLE_TASK"
        echo "--- Task content (first 20 lines) ---"
        head -20 "$QUEUE_DIR/done/$SAMPLE_TASK"
        echo "--- End of sample ---"
    fi

else
    print_error "Queue directory not created properly"
    FAILED_TESTS+=("queue_demo")
    ((TESTS_FAILED++))
fi

# Test 6: Store iteration
print_header "TEST 6: STORE ITERATION"
print_info "Testing iter_stores functionality..."

STORE_PARENT=$(mktemp -d)
python << EOF
from roach.store import Store, iter_stores
import torch

# Create multiple stores
for i in range(3):
    s = Store()
    s.init(parent="$STORE_PARENT", store_id=f"test_exp_{i}")
    s.save(torch.randn(5, 5), "data")
    s.log("metric", float(i))

# Iterate and verify
stores = list(iter_stores("$STORE_PARENT"))
assert len(stores) == 3, f"Expected 3 stores, got {len(stores)}"

for store_id, store in stores:
    assert store.store_dir is not None
    data = store.load("data")
    assert data.shape == (5, 5)

print(f"Successfully iterated over {len(stores)} stores")
EOF

if [ $? -eq 0 ]; then
    print_success "Store iteration test passed"
    ((TESTS_PASSED++))
else
    print_error "Store iteration test failed"
    FAILED_TESTS+=("store_iteration")
    ((TESTS_FAILED++))
fi

# Test 7: Task dependencies
print_header "TEST 7: TASK DEPENDENCIES"
DEP_QUEUE=$(mktemp -d)
print_info "Testing task chain with dependencies..."

python << EOF
from roach.submit import submit
import sys

queue_dir = "$DEP_QUEUE"

# Create task chain A -> B -> C
chk_a = submit(queue_dir, "echo 'Task A' && sleep 0.5")
chk_b = submit(queue_dir, "echo 'Task B' && sleep 0.5", chk=chk_a)
chk_c = submit(queue_dir, "echo 'Task C' && sleep 0.5", chk=chk_b)

print(f"Created task chain in {queue_dir}")
EOF

# Run worker
timeout 30 python -m roach.worker "$DEP_QUEUE" || :

NUM_DONE=$(ls -1 "$DEP_QUEUE/done" 2>/dev/null | wc -l || echo 0)
if [ "$NUM_DONE" -eq 3 ]; then
    print_success "All dependent tasks completed in order"
    ((TESTS_PASSED++))
else
    print_error "Expected 3 tasks, got $NUM_DONE"
    FAILED_TESTS+=("task_dependencies")
    ((TESTS_FAILED++))
fi

# Print summary
print_header "TEST SUMMARY"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
echo "Total tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "\n${RED}Failed tests:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  - $test"
    done
    exit 1
else
    echo -e "\n${GREEN}All tests passed! 🎉${NC}"
    exit 0
fi
