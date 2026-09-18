import sys

from roach.skill import reconcile

print("\n".join(reconcile(sys.argv[1] if len(sys.argv) > 1 else None)))
