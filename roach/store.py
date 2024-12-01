from datetime import datetime
from pathlib import Path
import struct
import tempfile
import time
from types import SimpleNamespace

import torch


def make_store_id():
    now = datetime.now()
    nanos = str(time.time_ns() % 1_000_000_000).zfill(9)
    return f"store_{now.strftime('%Y%m%d_%H%M%S')}_{nanos}"


class Store:
    def __init__(self, store_dir=None):
        self.store_dir = store_dir

    def init(self, parent=None, store_id=None):
        if parent is None:
            parent = tempfile.mkdtemp()
        if store_id is None:
            store_id = make_store_id()
        self.store_dir = f"{parent}/{store_id}"
        print(f"roach store_dir is {self.store_dir}")

    def save(self, obj, key, allow_overwrite=False):
        assert self.store_dir is not None

        path = f"{self.store_dir}/{key}.pt"
        if Path(path).exists() and not allow_overwrite:
            raise ValueError(f"key {key} already exists")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(obj, path)

    def log(self, key, val):
        assert self.store_dir is not None

        path = f"{self.store_dir}/{key}.bin"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "ab") as f:
            val = float(val)
            val_bytes = struct.pack("f", val)
            f.write(val_bytes)

    def load(self, key):
        assert self.store_dir is not None

        files = list(Path(self.store_dir).glob(f"{key}.*"))
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
            out_list = struct.unpack(f"{num_floats}f", val_bytes)
            out_tensor = torch.tensor(out_list)
            return out_tensor

    def ls(self, pattern="*"):
        return [
            p.relative_to(self.store_dir).name
            for p in Path(self.store_dir).glob(pattern)
        ]


def iter_stores(parent):
    for path in sorted(Path(parent).glob("*")):
        yield path.name, Store(path)


store = Store()
scratch = SimpleNamespace()
