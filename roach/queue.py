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


class Queue:
    def __init__(self, queue_dir):
        self.queue_dir = Path(queue_dir).expanduser()

    def submit(self, cmd, chk="true"):
        task_id = make_task_id()
        task_file = f"{self.queue_dir}/ready/{task_id}"
        Path(task_file).parent.mkdir(parents=True, exist_ok=True)

        with open(task_file, "w") as f:
            f.write(chk)
            f.write("\n---\n")
            f.write(cmd)

        done_file = f"{self.queue_dir}/done/{task_id}"
        return f"test -f '{done_file}'"
