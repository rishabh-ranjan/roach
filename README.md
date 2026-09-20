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
dependencies = ["roach @ git+https://github.com/rishabh-ranjan/roach@v0.5.6"]
```

Then, if you want them, link the [Claude Code skills](#claude-code-skills)
into your clone:

```bash
pixi run python -m roach.skill
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

## ilctop

`ilctop`: GPUs, CPUs and jobs on the ILC cluster at a glance -- who holds which
card under which qos, what is free, and live utilisation of your own jobs.
`ilctop -w` refreshes; `ilctop --json` prints the same data as records, for
scripts and agents. Installed with the package: `pixi run ilctop`.

## claude code skills

The package ships [Claude Code skills](roach/skill): `roach-slurm` for driving
`roach.slurm` and `roach-paper` for making figures and tables with
`roach.paper`. Nothing installs them for you: each person
links them into their own clone, by hand, if they want Claude to use them
there. They are never installed globally, so each clone's skills match its own
`roach`, and never committed, so a collaborator who has not asked for them
does not get them:

```bash
pixi run python -m roach.skill
```

```
.claude/skills/roach-slurm -> ../../.pixi/envs/default/lib/python3.12/site-packages/roach/skill/roach-slurm
```

Keep `.claude/` in the project's `.gitignore`. The links point at the
installed package rather than copying it: bumping `roach` in the environment
updates the skills, with nothing to re-run. Re-run the command only when the
link path itself changes -- a new python minor version, a renamed
environment, or a `roach` release that adds, renames or removes a skill.

Re-running reconciles: it adds missing links and removes stale ones. A link is
roach's if its target runs through `roach/skill/`; anything else in
`.claude/skills/` is left alone, and a real directory in a skill's place is
skipped. The project is the nearest parent of the working directory with a
`pyproject.toml`, `pixi.toml` or `.git`; pass a directory to override.

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
