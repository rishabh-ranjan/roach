#!/usr/bin/env python3
"""
Comprehensive example demonstrating roach Queue and Worker capabilities.

This script demonstrates:
- Task submission with and without preconditions
- Task dependencies and chaining
- Worker lifecycle
- Task state transitions
- Precondition checks
"""

import sys
import time
import tempfile
from pathlib import Path

from roach.submit import submit


def print_queue_status(queue_dir):
    """Print current status of the queue."""
    queue_dir = Path(queue_dir)

    states = ["queued", "active", "done", "failed", "paused", ".checking"]
    counts = {}

    for state in states:
        state_dir = queue_dir / state
        if state_dir.exists():
            counts[state] = len(list(state_dir.iterdir()))
        else:
            counts[state] = 0

    print("\nQueue Status:")
    print(f"  Queued: {counts['queued']}")
    print(f"  Checking: {counts['.checking']}")
    print(f"  Active: {counts['active']}")
    print(f"  Done: {counts['done']}")
    print(f"  Failed: {counts['failed']}")
    print(f"  Paused: {counts['paused']}")


def demo_basic_tasks(queue_dir):
    """Demonstrate basic task submission."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Task Submission")
    print("="*60)

    # Simple task without precondition
    cmd1 = "echo 'Hello from task 1' && sleep 1"
    chk1 = submit(queue_dir, cmd1)
    print(f"Submitted task 1: {cmd1}")
    print(f"  Check command: {chk1}")

    # Task with always-true precondition
    cmd2 = "echo 'Hello from task 2' && sleep 1"
    chk2 = submit(queue_dir, cmd2, chk="true")
    print(f"\nSubmitted task 2 with precondition 'true': {cmd2}")

    # Task with custom precondition
    cmd3 = "echo 'Task 3 executed after checking' && sleep 1"
    chk3 = submit(queue_dir, cmd3, chk="test -d /tmp")
    print(f"\nSubmitted task 3 with precondition 'test -d /tmp': {cmd3}")

    print_queue_status(queue_dir)


def demo_chained_tasks(queue_dir):
    """Demonstrate task dependencies using preconditions."""
    print("\n" + "="*60)
    print("DEMO 2: Chained Tasks with Dependencies")
    print("="*60)

    # Task A: Create a marker file
    marker_file = f"/tmp/roach_demo_marker_{int(time.time())}"
    cmd_a = f"echo 'Task A running' && touch {marker_file} && sleep 1"
    chk_a = submit(queue_dir, cmd_a)
    print(f"Submitted Task A (creates marker): {marker_file}")

    # Task B: Depends on Task A completion
    cmd_b = f"echo 'Task B running (depends on A)' && sleep 1"
    chk_b = submit(queue_dir, cmd_b, chk=chk_a)
    print(f"Submitted Task B (depends on A)")
    print(f"  Precondition: {chk_a}")

    # Task C: Depends on Task B completion
    cmd_c = f"echo 'Task C running (depends on B)' && rm {marker_file} && sleep 1"
    chk_c = submit(queue_dir, cmd_c, chk=chk_b)
    print(f"Submitted Task C (depends on B)")
    print(f"  Precondition: {chk_b}")

    print("\nTask chain: A -> B -> C")
    print_queue_status(queue_dir)


def demo_failing_precondition(queue_dir):
    """Demonstrate tasks with failing preconditions."""
    print("\n" + "="*60)
    print("DEMO 3: Failing Preconditions")
    print("="*60)

    # Task with a precondition that will fail initially
    nonexistent_file = f"/tmp/roach_will_not_exist_{int(time.time())}"
    cmd = f"echo 'This will not run immediately'"
    chk = f"test -f {nonexistent_file}"

    submit(queue_dir, cmd, chk=chk)
    print(f"Submitted task with failing precondition: {chk}")
    print("This task will remain queued until the precondition is met")

    print_queue_status(queue_dir)


def demo_parallel_tasks(queue_dir):
    """Demonstrate multiple independent tasks."""
    print("\n" + "="*60)
    print("DEMO 4: Parallel Independent Tasks")
    print("="*60)

    for i in range(5):
        cmd = f"echo 'Parallel task {i}' && sleep 1"
        submit(queue_dir, cmd)
        print(f"Submitted parallel task {i}")

    print("\nAll tasks can run in parallel (if multiple workers)")
    print_queue_status(queue_dir)


def demo_multiline_commands(queue_dir):
    """Demonstrate tasks with multiline commands."""
    print("\n" + "="*60)
    print("DEMO 5: Multiline Commands")
    print("="*60)

    cmd = """
echo 'Starting multiline task'
for i in 1 2 3; do
    echo "  Iteration $i"
    sleep 0.2
done
echo 'Multiline task complete'
"""
    submit(queue_dir, cmd)
    print("Submitted task with multiline bash script")

    print_queue_status(queue_dir)


def demo_python_tasks(queue_dir):
    """Demonstrate running Python commands as tasks."""
    print("\n" + "="*60)
    print("DEMO 6: Python Tasks")
    print("="*60)

    # Python one-liner
    cmd1 = "python3 -c 'import math; print(f\"Pi is approximately {math.pi:.6f}\")'"
    submit(queue_dir, cmd1)
    print("Submitted Python one-liner task")

    # Python with imports
    cmd2 = """
python3 << 'PYEOF'
import sys
import time

print(f"Python version: {sys.version}")
print("Sleeping for 0.5 seconds...")
time.sleep(0.5)
print("Python task complete!")
PYEOF
"""
    submit(queue_dir, cmd2)
    print("Submitted Python heredoc task")

    print_queue_status(queue_dir)


def demo_task_with_store(queue_dir):
    """Demonstrate integrating queue with store."""
    print("\n" + "="*60)
    print("DEMO 7: Integration with Store")
    print("="*60)

    store_parent = tempfile.mkdtemp(prefix="roach_queue_store_")

    cmd = f"""
python3 << 'PYEOF'
from roach.store import Store
import torch

store = Store()
store.init(parent="{store_parent}", store_id="queue_experiment")

# Simulate some work
data = torch.randn(10, 10)
store.save(data, "queue_generated_data")

# Log some metrics
for i in range(5):
    store.log("metric", float(i * 0.5))

print(f"Saved data to {{store.store_dir}}")
print("Store contents:", store.ls())
PYEOF
"""
    submit(queue_dir, cmd)
    print(f"Submitted task that uses Store")
    print(f"Store will be created at: {store_parent}")

    print_queue_status(queue_dir)


def demo_error_handling(queue_dir):
    """Demonstrate task failure handling."""
    print("\n" + "="*60)
    print("DEMO 8: Error Handling")
    print("="*60)

    # Task that will succeed
    cmd_success = "echo 'This task will succeed' && exit 0"
    submit(queue_dir, cmd_success)
    print("Submitted task that will succeed")

    # Task that will fail
    cmd_fail = "echo 'This task will fail' && exit 1"
    submit(queue_dir, cmd_fail)
    print("Submitted task that will fail")

    # Task that will fail with error message
    cmd_fail2 = "echo 'Error: Something went wrong' >&2 && exit 1"
    submit(queue_dir, cmd_fail2)
    print("Submitted task that will fail with error message")

    print("\nFailed tasks will be moved to failed/ directory")
    print_queue_status(queue_dir)


def print_instructions(queue_dir):
    """Print instructions for running the worker."""
    print("\n" + "="*60)
    print("WORKER INSTRUCTIONS")
    print("="*60)
    print(f"\nQueue directory: {queue_dir}")
    print("\nTo run the worker, use one of these commands:")
    print(f"\n1. Run one task and exit:")
    print(f"   python -m roach.worker {queue_dir} --one-task")
    print(f"\n2. Run all tasks and exit:")
    print(f"   python -m roach.worker {queue_dir}")
    print(f"\n3. Run as persistent worker (keeps running):")
    print(f"   python -m roach.worker {queue_dir} --persist")
    print("\nTo monitor the queue:")
    print(f"   watch -n 1 'ls -la {queue_dir}/{{queued,active,done,failed}}'")
    print("\nTo pause a task:")
    print(f"   mv {queue_dir}/active/<task_id> {queue_dir}/paused/")
    print("\nTo resume a paused task:")
    print(f"   mv {queue_dir}/paused/<task_id> {queue_dir}/active/")


def main():
    """Main function running all demonstrations."""
    print("="*60)
    print("ROACH QUEUE COMPREHENSIVE DEMONSTRATION")
    print("="*60)

    # Create temporary queue directory
    queue_dir = tempfile.mkdtemp(prefix="roach_queue_demo_")
    print(f"\nUsing queue directory: {queue_dir}")

    # Run all demonstrations
    demo_basic_tasks(queue_dir)
    demo_chained_tasks(queue_dir)
    demo_failing_precondition(queue_dir)
    demo_parallel_tasks(queue_dir)
    demo_multiline_commands(queue_dir)
    demo_python_tasks(queue_dir)
    demo_task_with_store(queue_dir)
    demo_error_handling(queue_dir)

    # Print final status and instructions
    print_queue_status(queue_dir)
    print_instructions(queue_dir)

    print("\n" + "="*60)
    print("DEMONSTRATION COMPLETE")
    print("="*60)
    print("\nTasks have been submitted. Run a worker to execute them.")

    return queue_dir


if __name__ == "__main__":
    queue_dir = main()

    # If --run-worker flag is provided, automatically run the worker
    if len(sys.argv) > 1 and sys.argv[1] == "--run-worker":
        print("\nStarting worker to execute all tasks...")
        import subprocess
        subprocess.run([sys.executable, "-m", "roach.worker", queue_dir])
