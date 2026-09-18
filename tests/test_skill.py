import os
import re

import pytest

from roach.skill import SRC, reconcile

SKILLS = sorted(d for d in SRC.iterdir() if (d / "SKILL.md").exists())


@pytest.mark.parametrize("skill", SKILLS, ids=lambda d: d.name)
def test_name_matches_directory(skill):
    text = (skill / "SKILL.md").read_text()
    assert re.search(r"^name: (.+)$", text, re.M).group(1) == skill.name


@pytest.mark.parametrize("skill", SKILLS, ids=lambda d: d.name)
def test_relative_links_resolve(skill):
    for md in skill.rglob("*.md"):
        text = md.read_text()
        targets = re.findall(r"\]\(([^)#]+)", text)
        targets += re.findall(r"`((?:scripts|clusters|references)/[^`<>* ]+)`", text)
        for target in targets:
            if "://" in target:
                continue
            assert (md.parent / target).exists() or (skill / target).exists(), (
                md,
                target,
            )


def test_reconcile(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "mine").mkdir()
    (skills / "other").symlink_to("/opt/other/skills/other")
    (skills / "roach").symlink_to("/old/env/site-packages/roach/skill")
    (skills / "roach-gone").symlink_to("/old/env/site-packages/roach/skill/roach-gone")
    (skills / SKILLS[0].name).symlink_to(f"/old/env/roach/skill/{SKILLS[0].name}")

    reconcile(tmp_path)

    assert (skills / "mine").is_dir()
    assert os.readlink(skills / "other") == "/opt/other/skills/other"
    assert not (skills / "roach").is_symlink()
    assert not (skills / "roach-gone").is_symlink()
    for skill in SKILLS:
        assert os.readlink(skills / skill.name) == str(skill)
    assert reconcile(tmp_path) == []
