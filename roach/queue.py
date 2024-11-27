from datetime import datetime
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import time
import psutil


def make_task_id():
    now = datetime.now()
    nanos = str(time.time_ns() % 1_000_000_000).zfill(9)
    return f"task_{now.strftime('%Y%m%d_%H%M%S')}_{nanos}"


class Queue:
    def __init__(self, queue_dir):
        self.queue_dir = queue_dir

    def submit(self, cmd, requires="true"):
        assert "\n" not in cmd
        assert "\n" not in requires

        task_id = make_task_id()
        task_file = f"{self.queue_dir}/ready/{task_id}"
        Path(task_file).parent.mkdir(parents=True, exist_ok=True)

        with open(task_file, "w") as f:
            f.write(cmd)
            f.write("\n")
            f.write(requires)
            f.write("\n")

        return task_file


SLEEP_TIME = 1


def worker(queue_dir):
    # worker is meant to be run in the background
    # hence,
    # - no logging: check state directly from queue dir
    # - no interrupt handling: kill with SIGTERM

    # make state dirs
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
            time.sleep(SLEEP_TIME)
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
            time.sleep(SLEEP_TIME)
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
                    # task file was moved
                    # kill subprocess
                    for child in psutil.Process(proc.pid).children(recursive=True):
                        child.kill()
                    proc.kill()
                    break
                time.sleep(SLEEP_TIME)
            else:
                if proc.poll() == 0:
                    # task completed
                    task_file.rename(f"{queue_dir}/done/{task_name}")
                else:
                    # task failed
                    task_file.rename(f"{queue_dir}/failed/{task_name}")
