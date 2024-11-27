from datetime import datetime
from pathlib import Path
import struct
import time
from types import SimpleNamespace

import torch


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

    def save(self, obj, key):
        path = f"{self.root}/{key}.pt"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(obj, path)

    def log(self, key, val):
        path = f"{self.root}/{key}.bin"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "ab") as f:
            val = float(val)
            val_bytes = struct.pack("f", val)
            f.write(val_bytes)

    def load(self, key):
        files = list(Path(self.root).glob(f"{key}.*"))
        assert len(files) > 0
        assert len(files) <= 1
        path = files[0]
        fname = Path(path).name

        if fname.endswith(".pt"):
            return torch.load(path, map_location="cpu", weights_only=False)

        elif fname.endswith(".bin"):
            with open(path, "rb") as f:
                val_bytes = f.read()
            num_floats = len(val_bytes) // 4
            return struct.unpack(f"{num_floats}f", val_bytes)

    def ls(self, pattern="*"):
        return [p.relative_to(self.root).name for p in Path(self.root).glob(pattern)]


roach = Roach()
scratch = SimpleNamespace()


def iter_roaches(parent):
    for path in sorted(Path(parent).glob("*")):
        yield path.name, Roach(path)
