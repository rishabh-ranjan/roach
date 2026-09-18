import sys

from roach.skill import hook, reconcile

args = [a for a in sys.argv[1:] if a != "--hook"]
root = args[0] if args else None
log = reconcile(root)
if "--hook" in sys.argv:
    log += hook(root)
print("\n".join(log))
