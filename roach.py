import os
from pathlib import Path
import signal
import socket
import subprocess
import time

import fire
import torch


class Store:
    def __init__(self, store_dir, device="cpu"):
        self.store_dir = store_dir
        self.device = device
        Path(store_dir).mkdir(parents=True, exist_ok=True)

    def __setitem__(self, key, val):
        store_file = f"{self.store_dir}/{key}.pt"
        Path(store_file).parent.mkdir(parents=True, exist_ok=True)
        torch.save(val, store_file)

    def __getitem__(self, key):
        store_file = f"{self.store_dir}/{key}.pt"
        return torch.load(store_file, map_location=self.device)


store = None


def init(project, store_root="/lfs/local/0/ranjanr/stores"):
    global store
    ts = time.time_ns()
    store_dir = f"{store_root}/{project}/{ts}"
    store = Store(store_dir)


def finish():
    store["done"] = True


def submit(queue, cmd, queue_root="/lfs/local/0/ranjanr/queues"):
    assert "\n" not in cmd

    ts = time.time_ns()
    task_file = f"{queue_root}/{queue}/ready/{ts}"
    Path(task_file).parent.mkdir(parents=True, exist_ok=True)

    with open(task_file, "w") as f:
        f.write(cmd)
        f.write("\n")


def worker(queue, sleep_time=1, queue_root="/lfs/local/0/ranjanr/queues"):
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
        task_iter = Path(f"{queue_dir}/ready").iterdir()
        try:
            task_file = min(task_iter)
        except ValueError:
            time.sleep(sleep_time)
            continue
        task_name = Path(task_file).name

        # killing worker should move task back to ready dir
        def handler(signum, frame):
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

        # run task
        with open(task_file, "r") as f:
            # first line of task file is the shell command
            # remove trailing newline
            cmd = f.readline().strip()
        try:
            # line buffering
            with open(task_file, "a", buffering=1) as f:
                f.write(f"\n=== {worker_name} ===\n")
                subprocess.run(cmd, shell=True, stdout=f, stderr=f, check=True)
        except subprocess.CalledProcessError:
            # task failed
            task_file.rename(f"{queue_dir}/failed/{task_name}")
        else:
            # task completed
            task_file.rename(f"{queue_dir}/done/{task_name}")


if __name__ == "__main__":
    fire.Fire()
