from datetime import datetime
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time
import psutil


def make_task_id():
    now = datetime.now()
    nanos = str(time.time_ns() % 1_000_000_000).zfill(9)
    return f"task_{now.strftime('%Y%m%d_%H%M%S')}_{nanos}"


def make_worker_id():
    now = datetime.now()
    hostname = socket.gethostname().split(".")[0]
    pid = os.getpid()
    return f"worker_{now.strftime('%Y%m%d_%H%M%S')}_{hostname}_{pid}"


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

    worker_id = make_worker_id()

    # worker loop
    while True:
        # select task
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

        def handler(signum, frame):
            # move back to ready dir
            task_dir.rename(f"{queue_dir}/ready/{task_id}")
            sys.exit(0)

        # register handlers
        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)

        # run task
        # line buffering
        Path(f"{task_dir}/{worker_id}").mkdir(parents=True, exist_ok=True)
        Path(f"{task_dir}/{worker_id}").mkdir(parents=True, exist_ok=True)
        with (
            open(f"{task_dir}/{worker_id}/out", "w", buffering=1) as out_f,
            open(f"{task_dir}/{worker_id}/err", "w", buffering=1) as err_f,
        ):
            proc = subprocess.Popen(f"{task_dir}/cmd", stdout=out_f, stderr=err_f)

            def handler(signum, frame):
                # kill subprocess and its children
                for child in psutil.Process(proc.pid).children(recursive=True):
                    child.kill()
                proc.kill()
                task_dir.rename(f"{queue_dir}/ready/{task_id}")
                sys.exit(0)

            # register handlers
            signal.signal(signal.SIGTERM, handler)
            signal.signal(signal.SIGINT, handler)

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
