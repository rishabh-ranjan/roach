from datetime import datetime
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import psutil

import yagmail


# https://psutil.readthedocs.io/en/latest/index.html#kill-process-tree
def kill_proc_tree(
    pid, sig=signal.SIGTERM, include_parent=True, timeout=None, on_terminate=None
):
    """Kill a process tree (including grandchildren) with signal
    "sig" and return a (gone, still_alive) tuple.
    "on_terminate", if specified, is a callback function which is
    called as soon as a child terminates.
    """
    assert pid != os.getpid(), "won't kill myself"
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    if include_parent:
        children.append(parent)
    for p in children:
        try:
            p.send_signal(sig)
        except psutil.NoSuchProcess:
            pass
    gone, alive = psutil.wait_procs(children, timeout=timeout, callback=on_terminate)
    return (gone, alive)


SLEEP_TIME = 1
SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


def make_worker_id():
    now = datetime.now()
    hostname = socket.gethostname().split(".")[0]
    pid = os.getpid()
    return f"worker_{now.strftime('%Y%m%d_%H%M%S')}_{hostname}_{pid}_gpus={os.environ.get('CUDA_VISIBLE_DEVICES')}"


class Worker:
    def __init__(self, queue_dir, mailto=None, persist=True, one_task=False):
        self.queue_dir = Path(queue_dir).expanduser()
        # task state dirs
        for name in ["queued", "checking", "active", "done", "failed", "paused"]:
            Path(f"{self.queue_dir}/tasks/{name}").mkdir(parents=True, exist_ok=True)
        # worker state dirs
        for name in ["idle", "active", "dead"]:
            Path(f"{self.queue_dir}/workers/{name}").mkdir(parents=True, exist_ok=True)

        self.worker_id = make_worker_id()
        self.worker_file = Path(f"{self.queue_dir}/workers/idle/{self.worker_id}")
        self.mailto = mailto
        self.persist = persist
        self.one_task = one_task
        self.notify_done = True
        self.notify_failed = True

        self.worker_file.touch()
        self.wlog(f"started: {self.worker_id}")

        for sig in SIGNALS:
            signal.signal(sig, self.default_handler)

        threading.Thread(target=self._watchdog, daemon=True).start()

        if mailto:
            with open("/dfs/user/ranjanr/.roach_gmail", "r") as f:
                password = f.read().strip()
            self.yag = yagmail.SMTP(user="roach.worker", password=password)
            self.yag.send(mailto, f"started: {self.worker_id}")

    def no_failed_tasks(self):
        return next(Path(f"{self.queue_dir}/tasks/failed").iterdir(), None) is None

    def no_active_tasks(self):
        return next(Path(f"{self.queue_dir}/tasks/active").iterdir(), None) is None

    def change_task_state(self, state):
        self.task_file = self.task_file.rename(
            f"{self.queue_dir}/tasks/{state}/{self.task_file.name}"
        )

    def change_worker_state(self, state):
        self.worker_file = self.worker_file.rename(
            f"{self.queue_dir}/workers/{state}/{self.worker_id}"
        )

    def wlog(self, msg, mail=False):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
        with open(self.worker_file, "a") as f:
            f.write(line)
            f.flush()
        print(line, end="", flush=True)
        if mail and self.mailto:
            try:
                self.yag.send(self.mailto, msg)
            except Exception as e:
                self.wlog(f"failed to send email: {e}")

    def die(self):
        self.change_worker_state("dead")
        sys.exit(0)

    def default_handler(self, signum, frame):
        self.die()

    def _watchdog(self):
        while True:
            time.sleep(SLEEP_TIME)
            try:
                os.utime(self.worker_file)
            except FileNotFoundError:
                # could be a race with main thread rename, or genuine removal
                if not self.worker_file.exists():
                    os.kill(os.getpid(), signal.SIGTERM)
                    return

    def check_precondition(self):
        """Run precondition. Returns True if passed, re-queues on failure."""
        with open(self.task_file, "r") as f:
            chk = ""
            for line in f:
                if line.startswith("---"):
                    break
                chk += line

        chk_proc = subprocess.Popen(chk, shell=True)

        def chk_handler(signum, frame):
            chk_proc.kill()
            self.change_task_state("queued")
            self.die()

        for sig in SIGNALS:
            signal.signal(sig, chk_handler)

        while chk_proc.poll() is None:
            time.sleep(SLEEP_TIME)

        if chk_proc.poll() != 0:
            self.wlog(f"check failed: {self.task_file.name}")
            self.change_task_state("queued")
            return False
        return True

    def task_path(self, state):
        return Path(f"{self.queue_dir}/tasks/{state}/{self.task_file.name}")

    def run_task(self):
        """Move task to active and execute it."""
        self.change_task_state("active")
        task_id = self.task_file.name
        self.wlog(f"running: {task_id}")

        with open(self.task_file, "r") as f:
            for line in f:
                if line.startswith("---"):
                    break
            cmd = ""
            for line in f:
                if line.startswith("==="):
                    break
                cmd += line

        f = open(self.task_file, "a")
        f.write(f"\n=== {self.worker_id} ===\n")
        f.flush()
        proc = subprocess.Popen(cmd, shell=True, stdout=f, stderr=f)
        f.close()  # subprocess has its own fd

        def proc_handler(signum, frame):
            kill_proc_tree(proc.pid, signal.SIGKILL)
            self.change_task_state("queued")
            self.die()

        for sig in SIGNALS:
            signal.signal(sig, proc_handler)

        while proc.poll() is None:
            if not self.task_file.exists():
                if self.task_path("paused").exists():
                    self.task_file = self.task_path("paused")
                    kill_proc_tree(proc.pid, signal.SIGSTOP, timeout=0)
                    self.wlog(f"paused: {task_id}")
                    while self.task_file.exists():
                        time.sleep(SLEEP_TIME)
                    if self.task_path("active").exists():
                        self.task_file = self.task_path("active")
                        kill_proc_tree(proc.pid, signal.SIGCONT, timeout=0)
                        self.wlog(f"resumed: {task_id}")
                    else:
                        kill_proc_tree(proc.pid, signal.SIGKILL)
                        self.wlog(f"killed (deleted while paused): {task_id}")
                        return
                else:
                    kill_proc_tree(proc.pid, signal.SIGKILL)
                    self.wlog(f"killed (deleted): {task_id}")
                    return
            time.sleep(SLEEP_TIME)

        # proc finished
        if proc.poll() == 0:
            self.change_task_state("done")
            self.wlog(f"done: {task_id}")
        else:
            self.change_task_state("failed")
            self.wlog(f"failed: {task_id}", mail=self.notify_failed)
            self.notify_failed = False

        if self.one_task:
            self.wlog("exiting (one_task=True)")
            self.die()

    def run(self):
        try:
            self._loop()
        except Exception:
            self.wlog(traceback.format_exc())
            self.die()

    def acquire_task(self):
        """Pick the first queued task whose precondition passes. Returns True if found."""
        queued_dir = Path(f"{self.queue_dir}/tasks/queued")
        if not queued_dir.exists():
            return False

        for self.task_file in sorted(queued_dir.iterdir()):
            try:
                self.change_task_state("checking")
            except FileNotFoundError:
                continue

            self.change_worker_state("active")
            self.wlog(f"checking: {self.task_file.name}")

            if self.check_precondition():
                return True

            self.change_worker_state("idle")
            for sig in SIGNALS:
                signal.signal(sig, self.default_handler)

        return False

    def _loop(self):
        while True:
            if self.no_failed_tasks():
                self.notify_failed = True

            if self.acquire_task():
                self.notify_done = True
                self.run_task()
                self.change_worker_state("idle")
                for sig in SIGNALS:
                    signal.signal(sig, self.default_handler)
            else:
                if self.no_active_tasks():
                    self.wlog(
                        f"({self.queue_dir.name}) queued + active = 0",
                        mail=self.notify_done,
                    )
                    self.notify_done = False
                if not self.persist:
                    self.wlog("no tasks, exiting (persist=False)")
                    self.die()

            time.sleep(SLEEP_TIME)


def worker(queue_dir, mailto=None, persist=True, one_task=False):
    Worker(queue_dir, mailto, persist, one_task).run()


if __name__ == "__main__":
    import strictfire

    strictfire.StrictFire(worker)
