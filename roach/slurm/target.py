"""Resolving ``"module:attr"`` to the function a job should run."""

from importlib import import_module
from typing import Any, Callable


def resolve(target: str) -> Callable[..., Any]:
    """``"mypkg.train:main"`` -> the function.

    Explicitly ``module:attr``: a dotted path alone is ambiguous when a module
    and a function share a name (``mypkg.train.main`` is both).
    """
    module, sep, attr = target.partition(":")
    if not sep:
        raise ValueError(f"target must be 'module:attr', got {target!r}")
    fn = getattr(import_module(module), attr)
    if not callable(fn):
        raise TypeError(f"{target} is not callable")
    return fn
