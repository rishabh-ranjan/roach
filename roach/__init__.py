from importlib.metadata import version

from roach.skill import reconcile

__version__ = version("roach")

try:
    reconcile()
except OSError:
    pass
