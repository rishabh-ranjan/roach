import inspect
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

import fire
import torch


# TODO: need to speed up access for filter, maybe by caching
class Store:
    def __init__(self, store_dir, device="cpu"):
        self.store_dir = store_dir
        self.device = device
        Path(store_dir).mkdir(parents=True, exist_ok=True)

    def __repr__(self):
        return f"Store('{self.store_dir}', '{self.device}')"

    def __setitem__(self, key, val):
        store_file = f"{self.store_dir}/{key}.pt"
        Path(store_file).parent.mkdir(parents=True, exist_ok=True)
        torch.save(val, store_file)

    def __getitem__(self, key):
        store_file = f"{self.store_dir}/{key}.pt"
        try:
            obj = torch.load(store_file, map_location=self.device)
            return obj
        except FileNotFoundError:
            store_dir = f"{self.store_dir}/{key}"
            store = Store(store_dir)
            return store


def get_caller_file():
    caller = inspect.currentframe().f_back.f_back
    # TODO: return full path
    file = caller.f_code.co_filename
    return file


store = None


def init(project, store_root="/lfs/local/0/ranjanr/stores"):
    global store
    timestamp = time.time_ns()
    store_dir = f"{store_root}/{project}/{timestamp}"
    store = Store(store_dir)
    store["__roach__"] = {
        "project": project,
        "timestamp": timestamp,
        "caller_file": get_caller_file(),
        "done": False,
    }
    # TODO: add start + end time (ISO format?). redundant with timestamp?


def finish():
    roach_dict = store["__roach__"]
    roach_dict["done"] = True
    store["__roach__"] = roach_dict


def scan(project, store_root="/lfs/local/0/ranjanr/stores"):
    project_dir = f"{store_root}/{project}"
    stores = []
    for store_dir in sorted(Path(project_dir).iterdir()):
        store = Store(store_dir)
        if store["__roach__"]["done"]:
            stores.append(store)
    return stores


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
        task_iter = Path(f"{queue_dir}/ready").iterdir()
        try:
            task_file = min(task_iter)
        except ValueError:
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

        # check requires
        try:
            with open(task_file, "a", buffering=1) as f:
                f.write(f"\n=== {worker_name}:requires ===\n")
                subprocess.run(requires, shell=True, stdout=f, stderr=f, check=True)
        except subprocess.CalledProcessError:
            # requires failed
            task_file.rename(f"{queue_dir}/ready/{task_name}")
            continue

        # run task
        try:
            # line buffering
            with open(task_file, "a", buffering=1) as f:
                f.write(f"\n=== {worker_name}:cmd ===\n")
                # TODO: print subprocess pid to allow killing
                # TODO: kill subprocess in the SIGTERM handler
                subprocess.run(cmd, shell=True, stdout=f, stderr=f, check=True)
        except subprocess.CalledProcessError:
            # task failed
            task_file.rename(f"{queue_dir}/failed/{task_name}")
        else:
            # task completed
            task_file.rename(f"{queue_dir}/done/{task_name}")


if __name__ == "__main__":
    fire.Fire()
