import sys
from pathlib import Path

MARKERS = ("pyproject.toml", "pixi.toml", ".git")


def project_root():
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        if any((d / m).exists() for m in MARKERS):
            return d
    return cwd


src = Path(__file__).resolve().parent
root = Path(sys.argv[1]) if len(sys.argv) > 1 else project_root()
skills = root / ".claude" / "skills"
skills.mkdir(parents=True, exist_ok=True)
stale = skills / "roach"
if stale.is_symlink() and stale.resolve() == src:
    stale.unlink()
for skill in sorted(d for d in src.iterdir() if (d / "SKILL.md").exists()):
    dst = skills / skill.name
    if dst.is_symlink():
        dst.unlink()
    elif dst.exists():
        sys.exit(f"{dst} exists and is not a symlink; remove it first")
    dst.symlink_to(skill)
    print(f"{dst} -> {skill}")
