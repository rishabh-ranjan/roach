import os
from pathlib import Path
import socket
import subprocess
import time

from colorama import Fore, Style
import fire
import torch


class Store:
    def __init__(self, store_dir, device="cpu"):
        self.store_dir = store_dir
        self.device = device
        Path(store_dir).mkdir(parents=True, exist_ok=True)

    def __setitem__(self, key, val):
        path = f"{self.store_dir}/{key}.pt"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(val, path)

    def __getitem__(self, key):
        path = f"{self.store_dir}/{key}.pt"
        return torch.load(path, map_location=self.device)


store_root = "/lfs/local/0/ranjanr/stores"
queue_root = "/lfs/local/0/ranjanr/queues"
sleep_time = 1
store = None


def init(project):
    global store
    ts = time.time_ns()
    store_dir = f"{store_root}/{project}/{ts}"
    store = Store(store_dir)


def finish():
    store["done"] = True


def submit(queue, cmd):
    assert "\n" not in cmd

    ts = time.time_ns()
    submit_path = f"{queue_root}/{queue}/ready/{ts}"
    Path(submit_path).parent.mkdir(parents=True, exist_ok=True)

    with open(submit_path, "w") as f:
        f.write(cmd)
        f.write("\n")


def worker(queue):
    hostname = socket.gethostname()
    pid = os.getpid()
    gpus = os.environ.get("CUDA_VISIBLE_DEVICES")
    worker_name = f"{hostname}:{pid}:{gpus}"
    prefix = f"[{worker_name}]"

    queue_dir = f"{queue_root}/{queue}"
    print(f"{prefix} queue at {queue_dir}")

    while True:
        tasks = list(Path(f"{queue_dir}/ready").iterdir())

        try:
            ready_path = min(tasks)
        except ValueError:
            time.sleep(sleep_time)
            continue

        task_name = ready_path.name

        Path(f"{queue_dir}/active").mkdir(exist_ok=True)
        try:
            active_path = ready_path.rename(f"{queue_dir}/active/{task_name}")
        except FileNotFoundError:
            print(
                f"{prefix} {Fore.YELLOW}failed to acquire task {task_name}{Style.RESET_ALL}"
            )
            time.sleep(SLEEP)
            continue

        print(f"{prefix} {Fore.BLUE}acquired task {task_name}{Style.RESET_ALL}")

        with open(active_path, "r") as f:
            task_str = f.readline().strip()

        try:
            with open(active_path, "a", buffering=1) as f:
                f.write(f"\n=== {worker_name} ===\n")
                subprocess.run(task_str, shell=True, stdout=f, stderr=f, check=True)

        except subprocess.CalledProcessError:
            Path(f"{queue_dir}/failed").mkdir(exist_ok=True)
            failed_path = active_path.rename(f"{queue_dir}/failed/{task_name}")
            print(f"{prefix} {Fore.RED}failed task {task_name}{Style.RESET_ALL}")

        except KeyboardInterrupt:
            Path(f"{queue_dir}/failed").mkdir(exist_ok=True)
            failed_path = active_path.rename(f"{queue_dir}/failed/{task_name}")
            print(f"{prefix} {Fore.RED}failed task {task_name}{Style.RESET_ALL}")
            break

        else:
            Path(f"{queue_dir}/done").mkdir(exist_ok=True)
            done_path = active_path.rename(f"{queue_dir}/done/{task_name}")
            print(f"{prefix} {Fore.GREEN}done task {task_name}{Style.RESET_ALL}")


if __name__ == "__main__":
    fire.Fire()
