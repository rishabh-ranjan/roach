import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import time


def submit(queue, cmd, requires="true", queue_root="/lfs/local/0/ranjanr/queues"):
    assert "\n" not in cmd
    assert "\n" not in requires

    timestamp = time.time_ns()
    task_file = f"{queue_root}/{queue}/ready/{timestamp}"
    Path(task_file).parent.mkdir(parents=True, exist_ok=True)

    with open(task_file, "w") as f:
        f.write(cmd)
        f.write("\n")
        f.write(requires)
        f.write("\n")

    return task_file


def worker(queue, sleep_time=1, queue_root="/lfs/local/0/ranjanr/queues"):
    # worker is meant to be run in the background
    # hence,
    # - no logging: check state directly from queue dir
    # - no interrupt handling: kill with SIGTERM

    # make state dirs
    queue_dir = f"{queue_root}/{queue}"
    for state in ["ready", "active", "done", "failed"]:
        state_dir = f"{queue_dir}/{state}"
        Path(state_dir).mkdir(parents=True, exist_ok=True)

    # worker name
    hostname = socket.gethostname()
    pid = os.getpid()
    gpus = os.environ.get("CUDA_VISIBLE_DEVICES")
    worker_name = f"{hostname}:{pid}:{gpus}"

    # worker loop
    while True:
        # select task
        task_file_list = sorted(Path(f"{queue_dir}/ready").iterdir())
        if len(task_file_list) == 0:
            # no task to run
            time.sleep(sleep_time)
            continue

        for task_file in task_file_list:
            # read task
            try:
                with open(task_file, "r") as f:
                    # first line of task file is the shell command
                    # remove trailing newline
                    cmd = f.readline().strip()
                    # second line of task file is the requires clause
                    # TODO: swap requires and cmd line order
                    requires = f.readline().strip()
            except FileNotFoundError:
                # task no longer exists
                # maybe another worker acquired it
                continue

            # check requires
            try:
                subprocess.run(requires, shell=True, check=True)
            except subprocess.CalledProcessError:
                # requires failed
                continue
            else:
                break
        else:
            # no task to run
            time.sleep(sleep_time)
            continue

        task_name = Path(task_file).name

        # killing worker should move task back to ready dir
        # TODO: there seems to be some bug here
        def handler(signum, frame):
            # FIXME: when we are here, task is already in done or failed dir
            # sigterm seems to wait for the subprocess to finish
            task_file.rename(f"{queue_dir}/ready/{task_name}")

        # register handler before moving to active dir
        signal.signal(signal.SIGTERM, handler)

        # acquire task
        try:
            task_file = task_file.rename(f"{queue_dir}/active/{task_name}")
        except FileNotFoundError:
            # task no longer exists
            # maybe another worker acquired it
            continue

        # read task
        with open(task_file, "r") as f:
            # first line of task file is the shell command
            # remove trailing newline
            cmd = f.readline().strip()
            # second line of task file is the requires clause
            requires = f.readline().strip()

        # run task
        # line buffering
        with open(task_file, "a", buffering=1) as f:
            f.write(f"\n=== {worker_name}:cmd ===\n")
            proc = subprocess.Popen(cmd, shell=True, stdout=f, stderr=f)

            def handler(signum, frame):
                proc.kill()
                task_file.rename(f"{queue_dir}/ready/{task_name}")

            # update SIGTERM handler to kill subprocess
            signal.signal(signal.SIGTERM, handler)

            while proc.poll() is None:
                if not Path(task_file).exists():
                    # task was moved to ready dir
                    # kill subprocess
                    proc.kill()
                    break
                time.sleep(1)

            if proc.poll() == 0:
                # task completed
                task_file.rename(f"{queue_dir}/done/{task_name}")
            else:
                # task failed
                task_file.rename(f"{queue_dir}/failed/{task_name}")
