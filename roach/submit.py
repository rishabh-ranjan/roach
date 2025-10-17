from datetime import datetime
from pathlib import Path
import time


def make_task_id():
    now = datetime.now()
    nanos = str(time.time_ns() % 1_000_000_000).zfill(9)
    return f"task_{now.strftime('%Y%m%d_%H%M%S')}_{nanos}"


def submit(queue_dir, cmd, chk="true"):
    queue_dir = Path(queue_dir).expanduser()
    task_id = make_task_id()
    task_file = f"{queue_dir}/queued/{task_id}"
    Path(task_file).parent.mkdir(parents=True, exist_ok=True)

    with open(task_file, "w") as f:
        f.write(chk)
        f.write("\n---\n")
        f.write(cmd)

    done_file = f"{queue_dir}/done/{task_id}"
    return f"test -f '{done_file}'"


if __name__ == "__main__":
    import strictfire

    strictfire.StrictFire(submit)
