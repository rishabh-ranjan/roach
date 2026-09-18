import json
import os
from pathlib import Path

MARKERS = ("pyproject.toml", "pixi.toml", ".git")
SRC = Path(__file__).resolve().parent


def project_root():
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        if any((d / m).exists() for m in MARKERS):
            return d
    return None


def owned(link):
    parts = Path(os.readlink(link)).parts
    return any(pair == ("roach", "skill") for pair in zip(parts, parts[1:]))


def reconcile(root=None):
    root = Path(root) if root is not None else project_root()
    if root is None:
        return []
    want = {d.name: d for d in SRC.iterdir() if (d / "SKILL.md").exists()}
    skills = root / ".claude" / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    log = []
    for link in skills.iterdir():
        if not link.is_symlink() or not owned(link):
            continue
        if str(want.get(link.name)) != os.readlink(link):
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


RUNNERS = (("pixi.lock", "pixi run "), ("pixi.toml", "pixi run "), ("uv.lock", "uv run "))
IMPORT = "python -c 'import roach'"


def hook(root=None):
    root = Path(root) if root is not None else project_root()
    if root is None:
        return []
    runner = next((r for f, r in RUNNERS if (root / f).exists()), "")
    path = root / ".claude" / "settings.json"
    settings = json.loads(path.read_text()) if path.exists() else {}
    start = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
    if any(IMPORT in h.get("command", "") for e in start for h in e.get("hooks", [])):
        return []
    command = f'cd "$CLAUDE_PROJECT_DIR" && {runner}{IMPORT}; true'
    start.append({"hooks": [{"type": "command", "timeout": 120, "command": command}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    return [f"{path}: SessionStart runs {runner}{IMPORT}"]
