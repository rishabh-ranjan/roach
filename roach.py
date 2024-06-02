from pathlib import Path
import time

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


def init(project, store_root="/lfs/local/0/ranjanr/stores"):
    ts = str(time.time_ns())
    store_dir = f"{store_root}/{project}/{ts}"
    store = Store(store_dir)
    return store


def finish(store):
    store["done"] = True
