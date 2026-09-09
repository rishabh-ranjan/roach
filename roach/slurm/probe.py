import os
import shutil
import socket
import subprocess


def main(seconds: int = 0) -> None:
    rank = os.environ.get("RANK", "-")
    gpus = shutil.which("nvidia-smi") and subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used", "--format=csv,noheader"],
        capture_output=True, text=True,
    ).stdout.strip().replace("\n", "; ") or "none"
    print(f"probe: rank={rank} host={socket.gethostname()} home={os.environ['HOME']} "
          f"tmpdir={os.environ.get('TMPDIR')} gpus=[{gpus}]", flush=True)
    if seconds:
        import time
        time.sleep(seconds)
