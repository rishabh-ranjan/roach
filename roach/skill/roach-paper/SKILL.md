---
name: roach-paper
description: Paper figures and tables through roach.paper (github.com/rishabh-ranjan/roach) — the figure design system (Inter, a fixed type scale, a reserved primary color, OKLCh shades, true-size saving, HTML diagram export) and LaTeX table helpers. Use whenever a matplotlib figure, plot, chart or LaTeX table is made or edited for a paper, poster or slides, or when roach.paper, figure fonts, colors, sizes or \includegraphics widths come up.
---

# roach paper

`roach.paper` is a figure design system: `paper.apply()` sets fonts, type
scale and chrome, and the save helpers make every figure render at true size
on the page. The rcParams do most of the work; this skill is the rules they
cannot enforce. A project's own `DESIGN.md`, if it has one, extends these and
wins where it is more specific.

```python
from roach import paper

paper.apply()
fig, ax = plt.subplots(figsize=(0.49 * paper.LINEWIDTH_IN, 1.4))
ax.plot(x, y_ours, color=paper.PRIMARY)
paper.save_at_width(fig, "figures/results/curve.pdf", 0.49 * paper.LINEWIDTH_IN)
```

## 1. True size

A figure is generated at the width of its `\includegraphics` slot, and included
at that same width, so LaTeX rescales nothing and a 7 pt label is 7 pt on the
page. A plain `bbox_inches="tight"` save crops every figure to a different
width, each then rescaled by a different factor: that is where inconsistent
font sizes between figures come from.

- `paper.save_at_width(fig, path, width_in)` pins the width and crops only
  vertically. The default. Content must fit inside `width_in`; reserve room
  for an outside legend in the layout.
- `paper.fit_to_width(fig, width_in, pad)` then `paper.save_fig(fig, path,
  pad)` with the same `pad`, for content that legitimately spans the whole
  slot. Call `fit_to_width` before any overlay that measures final geometry.
- `paper.LINEWIDTH_IN` is 5.5, `\linewidth` for NeurIPS and ICLR. For another
  venue, print `\the\linewidth` (72.27 pt per inch) and use that.
- The slot width is written once in the script and matches the
  `width=` in the `.tex`: `0.49 * LINEWIDTH_IN` with `width=0.49\linewidth`.

Save PDF, never PNG, for anything LaTeX includes.

## 2. Type

Every piece of text is one of `paper.TITLE_SIZE`, `LABEL_SIZE`, `LEGEND_SIZE`
(7 pt), `TICK_SIZE` (6 pt) or `FINE_SIZE` (5 pt, fine print, never data). No
literal font sizes. Emphasis is weight or darkness, not size. Titles are
regular weight. The font is Inter, vendored in the package and pinned; math is
STIX. Do not substitute Helvetica or Arial.

## 3. Color

Three roles, referred to by role name, never by hex or brand name:

- `paper.PRIMARY` (cardinal red, `#8C1515`) belongs to the paper's own
  method, whatever the paper calls it, and to nothing else: its curves,
  markers, and its name wherever the name is drawn, in bold. The LaTeX macro
  for the method name uses the same hex, so text and figures agree:
  `\definecolor{ours}{HTML}{8C1515}`,
  `\newcommand{\ours}{\textcolor{ours}{\textbf{Name}}}`.
- `paper.ACCENT` (palo alto green) marks the second thing the reader should
  see: the target, the task, the in-context part.
- `paper.NEUTRAL` (cool grey) is structure and non-focal elements;
  `paper.BLACK` the ink.
- Every other method gets one fixed muted color, defined once and reused
  identically in every figure of the paper.
- Lighter variants come from `paper.shades(hex)`, which returns `base`,
  `light` (OKLCh L 0.72) and `soft` (L 0.90) with hue held and chroma
  tapered, so a light green and a light red read as equally light. Use them
  for bands, fills and de-emphasized series; never hand-pick a tint.

## 3b. Hand-drawn diagrams

A schematic that matplotlib cannot draw is HTML/SVG on a fixed px canvas,
exported with `paper.html_to_pdf(src, path, canvas_w, canvas_h, width_in)`
(needs `playwright` and its chromium). Pick a canvas so 1 pt is a whole number
of px (4 px/pt for a 5.5 in figure is 1584 px wide) and express every font
size in that unit on the type scale above. Declare `font-family: 'Inter'`
and nothing else: the export injects the package's Inter, so the HTML carries
no font files or paths. Colors from `paper.shades` on the role constants.
Then read the PDF like any other figure.

## 4. Chrome

No top or right spines, axis lines and tick marks in `paper.AXIS_GREY` (tick
labels stay black), no legend frames, no grid unless it carries reading
value (then 0.5 pt). Data lines 0.75 to 1 pt. `apply()` sets all of these;
do not override them per figure.

## 5. Scripts

One script per figure, writing to the path the `.tex` includes. All
human-facing strings (panel titles, axis labels, legend names and grouping)
sit in one block of constants at the top of the script, so copy is edited in
one place. Run scripts through the project's environment (a pixi task per
figure).

## 6. Look at it

After every change, regenerate the figure and read the PDF itself (the Read
tool renders it). Check: no overlapping or clipped text, fonts are Inter,
sizes are on the scale, `PRIMARY` is only on our method, and `pdfinfo` reports
the slot width (`width_in * 72` pt). A figure that was not looked at is not
done.

## 7. Tables

Build the table body as a string of `&`-separated rows,
`paper.align_tex(body)` to column-align the source, `paper.save_tex(tex,
path)` to write it; the `.tex` `\input`s the body and keeps the caption and
`tabular` preamble. Numbers come from the same code that makes the figures,
never typed by hand. Our method's row or name uses the `\ours` macro.
