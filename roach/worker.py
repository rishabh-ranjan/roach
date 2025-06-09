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

SLEEP_TIME = 1


def make_worker_id():
    now = datetime.now()
    hostname = socket.gethostname().split(".")[0]
    pid = os.getpid()
    return f"worker_{now.strftime('%Y%m%d_%H%M%S')}_{hostname}_{pid}_gpus={os.environ.get('CUDA_VISIBLE_DEVICES')}"


def kill_family(proc):
    for child in psutil.Process(proc.pid).children(recursive=True):
        child.kill()
    proc.kill()


def worker(queue_dir):
    # worker is meant to be run in the background
    # hence,
    # - no logging: check state directly from queue dir
    # - no interrupt handling: kill with SIGTERM

    queue_dir = Path(queue_dir).expanduser()

    # make state dirs
    for state in ["ready", "check", "active", "done", "failed"]:
        state_dir = f"{queue_dir}/{state}"
        Path(state_dir).mkdir(parents=True, exist_ok=True)

    worker_id = make_worker_id()

    # worker loop
    while True:
        # snapshot of the queue
        task_file_list = sorted(Path(f"{queue_dir}/ready").iterdir())
        for task_file in task_file_list:
            task_id = Path(task_file).name

            # acquire task to check
            try:
                task_file = task_file.rename(f"{queue_dir}/check/{task_id}")
            except FileNotFoundError:
                # task no longer exists
                # maybe another worker acquired it
                continue

            # read check
            with open(task_file, "r") as f:
                chk = ""
                for line in f:
                    if line.startswith("---"):
                        break
                    chk += line

            # run check
            chk_proc = subprocess.Popen(chk, shell=True, stdout=f, stderr=f)
            while chk_proc.poll() is None:
                time.sleep(SLEEP_TIME)

            if chk_proc.poll() != 0:
                # check failed
                task_file.rename(f"{queue_dir}/ready/{task_id}")
                continue

            # check successful
            # run task
            task_file = task_file.rename(f"{queue_dir}/active/{task_id}")

            def handler(signum, frame):
                # move back to ready dir
                task_file.rename(f"{queue_dir}/ready/{task_id}")
                sys.exit(0)

            # register handlers
            signal.signal(signal.SIGTERM, handler)

            # read task
            with open(task_file, "r") as f:
                for line in f:
                    if line.startswith("---"):
                        break
                cmd = ""
                for line in f:
                    if line.startswith("==="):
                        break
                    cmd += line

            # run task
            # line buffering
            with open(task_file, "a", buffering=1) as f:
                f.write(f"\n=== {worker_id} ===\n")
                cmd_proc = subprocess.Popen(cmd, shell=True, stdout=f, stderr=f)

                def handler(signum, frame):
                    kill_family(cmd_proc)
                    task_file.rename(f"{queue_dir}/ready/{task_id}")
                    sys.exit(0)

                # kill process family on SIGTERM
                signal.signal(signal.SIGTERM, handler)

                while cmd_proc.poll() is None:
                    if not Path(task_file).exists():
                        # task file was moved
                        kill_family(cmd_proc)
                        break
                    time.sleep(SLEEP_TIME)
                else:
                    if cmd_proc.poll() == 0:
                        # task completed
                        task_file.rename(f"{queue_dir}/done/{task_id}")
                    else:
                        # task failed
                        task_file.rename(f"{queue_dir}/failed/{task_id}")

        # no more tasks to run for this snapshot of the queue
        time.sleep(SLEEP_TIME)
        continue


if __name__ == "__main__":
    import strictfire

    strictfire.StrictFire(worker)
