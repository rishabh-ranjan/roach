"""Job-side entry point: `python -m roach.slurm.run <module:attr> <args.json>`.

srun starts one of these per GPU. Everything rank-related happens here so the
target function stays an ordinary python function: it is called with exactly the
arguments the submitter passed, in every rank, and picks up the distributed
environment through the usual torch env vars.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from roach.slurm.target import resolve


def set_torch_dist_env() -> None:
    """Translate slurm's view of the step into torch's.

    srun already tells every task who it is, so there is no launcher to babysit
    and no rendezvous to configure -- and, unlike a torchrun agent, each rank is
    a slurm task, so preemption signals reach them directly.
    """
    if "SLURM_PROCID" not in os.environ:
        return  # running outside slurm: single process, torch defaults apply
    os.environ["RANK"] = os.environ["SLURM_PROCID"]
    os.environ["LOCAL_RANK"] = os.environ["SLURM_LOCALID"]
    os.environ["WORLD_SIZE"] = os.environ["SLURM_NTASKS"]
    os.environ.setdefault("MASTER_ADDR", _first_host())
    # Same port for every rank of a job, different across jobs on a node.
    os.environ.setdefault(
        "MASTER_PORT", str(20000 + int(os.environ["SLURM_JOB_ID"]) % 20000)
    )


def _first_host() -> str:
    nodelist = os.environ.get("SLURM_JOB_NODELIST", "")
    if not nodelist:
        return socket.gethostname()
    out = subprocess.run(
        ["scontrol", "show", "hostnames", nodelist],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.split()[0]


def main(argv: list[str]) -> None:
    target, args_path = argv[0], argv[1]
    args = json.loads(Path(args_path).read_text())
    set_torch_dist_env()
    resolve(target)(**args)


if __name__ == "__main__":
    main(sys.argv[1:])
