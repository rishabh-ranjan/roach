import sys
from pathlib import Path

src = Path(__file__).resolve().parent
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".claude"
dst = root / "skills" / "roach"
dst.parent.mkdir(parents=True, exist_ok=True)
if dst.is_symlink():
    dst.unlink()
elif dst.exists():
    sys.exit(f"{dst} exists and is not a symlink; remove it first")
dst.symlink_to(src)
print(f"{dst} -> {src}")
