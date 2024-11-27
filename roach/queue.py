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

    def submit(self, cmd):
        task_id = make_task_id()
        task_dir = f"{self.queue_dir}/ready/{task_id}"
        Path(task_dir).mkdir(parents=True, exist_ok=True)

        with open(f"{task_dir}/cmd", "w") as f:
            f.write(cmd)
        Path(f"{task_dir}/cmd").chmod(0o755)

        return task_dir


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
        # XXX: keep this inefficient loop, will need for precondition checks
        task_dir_list = sorted(Path(f"{queue_dir}/ready").iterdir())
        if len(task_dir_list) == 0:
            # no task to run
            time.sleep(SLEEP_TIME)
            continue

        task_dir = task_dir_list[0]
        task_id = Path(task_dir).name

        # acquire task
        try:
            task_dir = task_dir.rename(f"{queue_dir}/active/{task_id}")
        except FileNotFoundError:
            # task no longer exists
            # maybe another worker acquired it
            continue

        # run task
        # line buffering
        with open(f"{task_dir}/out", "a", buffering=1) as f:
            f.write(f"\n=== {worker_name}:cmd ===\n")
            proc = subprocess.Popen(f"{task_dir}/cmd", stdout=f, stderr=f)

            def handler(signum, frame):
                # kill subprocess and its children
                for child in psutil.Process(proc.pid).children(recursive=True):
                    child.kill()
                proc.kill()
                task_dir.rename(f"{queue_dir}/ready/{task_id}")

            # SIGTERM handler to kill subprocess
            signal.signal(signal.SIGTERM, handler)

            while proc.poll() is None:
                if not Path(task_dir).exists():
                    # task file was moved
                    # kill subprocess and its children
                    for child in psutil.Process(proc.pid).children(recursive=True):
                        child.kill()
                    proc.kill()
                    break
                time.sleep(SLEEP_TIME)
            else:
                if proc.poll() == 0:
                    # task completed
                    task_dir.rename(f"{queue_dir}/done/{task_id}")
                else:
                    # task failed
                    task_dir.rename(f"{queue_dir}/failed/{task_id}")
