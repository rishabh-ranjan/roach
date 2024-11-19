import base64
from datetime import datetime
import inspect
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import time

import fire
import torch
from tqdm.auto import tqdm


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


def make_run_id():
    now = datetime.now()
    nanos = str(time.time_ns() % 1_000_000_000).zfill(9)
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{nanos}"


class Roach:
    def __init__(self, root=None):
        self.root = root

    def init(self, parent):
        self.run_id = make_run_id()
        self.root = f"{parent}/{self.run_id}"

    def save(self, key, val):
        file = f"{self.root}/{key}.pt"
        Path(file).parent.mkdir(parents=True, exist_ok=True)
        torch.save(val, file)

    def log(self, key, val):
        file = f"{self.root}/{key}.bin"
        Path(file).parent.mkdir(parents=True, exist_ok=True)
        with open(file, "ab") as f:
            assert type(val) == float
            val_bytes = struct.pack("f", val)
            f.write(val_bytes)

    def load(self, key):
        files = list(Path(self.root).glob(f"{key}.*"))
        assert len(files) == 1
        file = files[0]
        fname = Path(file).name

        if fname.endswith(".pt"):
            return torch.load(file, map_location="cpu", weights_only=False)

        elif fname.endswith(".bin"):
            with open(file, "rb") as f:
                val_bytes = f.read()
            num_floats = len(val_bytes) // 4
            return struct.unpack(f"{num_floats}f", val_bytes)

    def ls(self, pattern="*"):
        return [p.relative_to(self.root).stem for p in Path(self.root).glob(pattern)]


roach = Roach()


def iter_roaches(parent):
    for path in sorted(Path(root).glob("*")):
        yield path.name, Roach(path)


if __name__ == "__main__":
    fire.Fire()
