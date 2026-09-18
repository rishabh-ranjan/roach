import os
from pathlib import Path

MARKERS = ("pyproject.toml", "pixi.toml", ".git")
SRC = Path(__file__).resolve().parent


def project_root():
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        if any((d / m).exists() for m in MARKERS):
            return d
    return cwd


def owned(link):
    parts = Path(os.readlink(link)).parts
    return any(pair == ("roach", "skill") for pair in zip(parts, parts[1:]))


def target(skill, root, skills):
    if skill.is_relative_to(root):
        return os.path.relpath(skill, skills)
    return str(skill)


def reconcile(root=None):
    root = (Path(root) if root is not None else project_root()).resolve()
    skills = root / ".claude" / "skills"
    want = {
        d.name: target(d, root, skills)
        for d in SRC.iterdir()
        if (d / "SKILL.md").exists()
    }
    skills.mkdir(parents=True, exist_ok=True)
    log = []
    for link in skills.iterdir():
        if not link.is_symlink() or not owned(link):
            continue
        if want.get(link.name) != os.readlink(link):
            link.unlink()
            log.append(f"removed {link}")
    for name, src in sorted(want.items()):
        dst = skills / name
        if dst.is_symlink():
            continue
        if dst.exists():
            log.append(f"skipped {dst}: exists and is not a roach link")
            continue
        dst.symlink_to(src)
        log.append(f"{dst} -> {src}")
    return log

