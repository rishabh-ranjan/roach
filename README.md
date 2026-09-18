# roach -- fearless experiment management

Per [wikipedia](https://en.wikipedia.org/wiki/Cockroach#Hardiness), roaches:
> * are capable of remaining active for a month without food
> * are able to survive on limited resources
> * can go without air for 45 minutes
> * have survived twelve hours at −5 to −8 °C (23 to 18 °F)
> * are also able to survive decapitation
> * will "inherit the Earth" if humanity destroys itself in a nuclear war

Same goes for `roach` experiments.

`roach` is an experiment management framework, intended primarily for use by
close collaborators and me.

## install

As a dependency, pinned to a tag:

```toml
# pyproject.toml
dependencies = ["roach @ git+https://github.com/rishabh-ranjan/roach@v0.1.1"]
```

For development:

```bash
git clone https://github.com/rishabh-ranjan/roach
cd roach
pixi install
pixi run test
```

## roach slurm

Run a python function on slurm -- one job, one rank per GPU, resumable across
preemption and the wall clock. **[roach/slurm/README.md](roach/slurm/README.md)**.

## claude code skills

The package ships [Claude Code skills](roach/skill): `roach-slurm` for driving
`roach.slurm` and `roach-paper` for making figures and tables with
`roach.paper`. They install themselves into the project that installs `roach`,
never globally, so each project's skills match its own `roach`:

```
<project>/.claude/skills/roach-* -> <site-packages>/roach/skill/roach-*
```

pip cannot run code at install time, so `import roach` does it: it reconciles
the links with the skills the installed package ships, silently, and touches
nothing when they are already right. The project is the nearest parent of the
working directory with a `pyproject.toml`, `pixi.toml` or `.git`.
`python -m roach.skill [project]` does the same by hand and prints what changed.

Reconciling adds missing links and removes stale ones: a renamed or removed
skill, a link into an old environment. A link is roach's if its target runs
through `roach/skill/`; anything else in `.claude/skills/` is left alone, and a
real directory in a skill's place is skipped. The links are absolute, so
gitignore `.claude/skills/roach-*`.

They are symlinks into the installed package: an editable install tracks the
clone (`git pull` updates it), a pinned install updates when the pin is
bumped.

A fresh clone has no links until something imports `roach`. To have the skills
from the first Claude Code session, run this once per project and commit
`.claude/settings.json`:

```bash
python -m roach.skill --hook
```

It adds a `SessionStart` hook that imports `roach` in the project's
environment (`pixi run`, `uv run` or plain `python`, by which lock file the
project has), so every collaborator gets it with the clone. Keep it in the
project, not in a user's global settings.

## roach paper

`roach.paper`: a figure design system for papers, plus save helpers for
figures and tables. `paper.apply()` before creating figures.

- **Fonts**: Inter (vendored in `roach/fonts/`, pinned so output is identical on
  any machine); STIX math; TrueType embedding.
- **Type scale** (print points): `LABEL_SIZE`/`TITLE_SIZE`/`LEGEND_SIZE` 7,
  `TICK_SIZE` 6, `FINE_SIZE` 5 (never data). Emphasis via weight and darkness,
  not size.
- **Palette**: `CARDINAL_RED` `#8C1515`, `PALO_ALTO` `#175E54`, `COOL_GREY`
  `#53565A`, `BLACK` `#1A1A1A`, `WHITE`. Cardinal red is reserved for the
  paper's own method, whatever it is named: use `paper.OURS` for its curves,
  markers and text, and the same hex for its name in LaTeX. Every other method
  gets one fixed muted color, reused identically across figures.
- **Chrome**: no top/right spines, no legend frames, 0.6 pt axes, 0.5 pt grid,
  1 pt data lines.
- **True-size saving**: generate each figure at its `\includegraphics` slot
  width so LaTeX applies no rescaling and point sizes render at true size.
  `save_at_width(fig, path, width_in)` pins the width and crops only
  vertically; for content that spans the full slot (e.g. an outside legend),
  `fit_to_width(fig, width_in, pad)` then `save_fig(fig, path, pad)`.
  `LINEWIDTH_IN = 5.5` is `\linewidth` for NeurIPS/ICLR.
- **Tables**: `save_tex`, `align_tex`.
