---
name: roach-paper
description: Paper figures and tables through roach.paper (github.com/rishabh-ranjan/roach) — the figure design system (Inter, a fixed type scale, a reserved primary color, true-size saving) for matplotlib plots, HTML/SVG diagrams and LaTeX tables. Use whenever a figure, plot, chart, diagram, schematic or LaTeX table is made or edited for a paper, poster or slides, or when roach.paper, figure fonts, colors, sizes or \includegraphics widths come up.
---

# roach paper

`roach.paper` is a figure design system shared by two different workflows:
**plots** (matplotlib, sections A) and **diagrams** (hand-written HTML/SVG,
section B). They share the design tokens in section 0 and nothing else. The
rcParams do most of the work for plots; this skill is the rules they cannot
enforce. A project's own `DESIGN.md`, if it has one, extends these and wins
where it is more specific.

roach is an unpinned git dependency (`roach = { git = "https://github.com/rishabh-ranjan/roach" }`
in `pixi.toml`); never add a `rev` or tag. `pixi update roach` moves the lock
to the latest commit; run it when a helper this skill names is missing.

## 0. Shared design tokens

**Width.** `paper.LINEWIDTH_IN` is 5.5, `\linewidth` for NeurIPS and ICLR.
For another venue, print `\the\linewidth` (72.27 pt per inch) and use that.
A figure is generated at the width of its `\includegraphics` slot and included
at that same width, so LaTeX rescales nothing and a 7 pt label is 7 pt on the
page. The slot width is written once in the script and matches the `width=`
in the `.tex`: `0.49 * LINEWIDTH_IN` with `width=0.49\linewidth`.

**Type.** Every piece of text is one of `paper.TITLE_SIZE`, `LABEL_SIZE`,
`LEGEND_SIZE` (7 pt), `TICK_SIZE` (6 pt) or `FINE_SIZE` (5 pt, fine print,
never data). No literal font sizes. Emphasis is weight or darkness, not size.
Titles are regular weight. The font is Inter, vendored in the package and
pinned; math is STIX. Do not substitute Helvetica or Arial.

**Color.** Three roles, referred to by role name, never by hex or brand name:

- `paper.PRIMARY` (cardinal red, `#8C1515`) belongs to the paper's own
  method, whatever the paper calls it, and to nothing else: its curves,
  markers, and its name wherever the name is drawn, in bold. The LaTeX macro
  for the method name uses the same hex, so text and figures agree:
  `\definecolor{ours}{HTML}{8C1515}`,
  `\newcommand{\ours}{\textcolor{ours}{\textbf{Name}}}`.
- `paper.ACCENT` (palo alto green) marks the second thing the reader should
  see: the target, the task, the in-context part.
- `paper.NEUTRAL` (cool grey) is structure and non-focal elements;
  `paper.BLACK` the ink, `paper.WHITE` the background.
- Every other method gets one fixed muted color, defined once and reused
  identically in every figure of the paper.
- Lighter variants come from `paper.shades(hex)`, which returns `base`,
  `light` (OKLCh L 0.72), `pale` (L 0.81) and `soft` (L 0.90) with hue held
  and chroma tapered, so a light green and a light red read as equally
  light. Use them for bands, fills and de-emphasized elements; never
  hand-pick a tint. `pale` is the fill for a box that carries black text.
- Text must stay legible on its fill: WCAG contrast
  (`paper.contrast(text, fill)`) of at least 4.5 for any text, 7 or more for
  labels at `FINE_SIZE`. Black on `pale` is about 9.5, black on `light` about
  7, black on `base` fails; put white text on `base` fills. Check every
  text-on-fill pair in the generator and fail the build when one drops below
  the bar, rather than judging it by eye.

**Look at it.** After every change, regenerate the figure and read the PDF
itself (the Read tool renders it). Check: no overlapping or clipped text,
fonts are Inter, sizes are on the scale, `PRIMARY` is only on our method, and
the page width is the slot width (`width_in * 72` pt). A figure that was not
looked at is not done. Save PDF, never PNG, for anything LaTeX includes.

**Look at it at high resolution.** A whole-figure render is downsampled
before you see it, which hides the defects that matter: baselines of small
caps, subscripts spilling out of shapes, touching glyphs, 1 to 2 px overlaps,
misaligned arrowheads, holes and seams where two shapes join. Rasterize the
PDF itself at 600 dpi or more
(`pdftoppm -r 600 -png -singlefile fig.pdf /tmp/fig`), never a browser
screenshot of the HTML; if `pdftoppm` is missing, add `poppler` to the pixi
environment rather than falling back. Judge defects from the tiles, never
from the downsampled whole.

- After the first render and after any structural change (layout, a new
  element, a moved panel), read every tile of about 1100 px on the long side
  (a 5.5 in figure at 600 dpi is a 3 × 2 grid).
- After a local edit, read only the tiles covering what changed, plus a crop
  of 8× or more of every join the edit touched: arrowheads on shafts, shapes
  abutting shapes, lines meeting borders. Check for holes, seams and corners
  poking out.

For a check whose answer is a number (a gap, a padding, an overflow, whether
two parts that should touch do), measure it in code (text bounding boxes from
the browser for diagrams, `get_window_extent` for matplotlib) rather than by
eye.

**A defect you saw is a defect you fix.** Never report a visible flaw as
minor, barely visible, or fixable on request. Fix it, re-render and look
again before replying. Ask only when the fix needs a design decision.

## A. Plots (matplotlib)

```python
from roach import paper

paper.apply()
fig, ax = plt.subplots(figsize=(0.49 * paper.LINEWIDTH_IN, 1.4))
ax.plot(x, y_ours, color=paper.PRIMARY)
paper.save_at_width(fig, "figures/results/curve.pdf", 0.49 * paper.LINEWIDTH_IN)
```

### A1. True size

A plain `bbox_inches="tight"` save crops every figure to a different width,
each then rescaled by a different factor: that is where inconsistent font
sizes between figures come from.

- `paper.save_at_width(fig, path, width_in)` pins the width and crops only
  vertically. The default. Content must fit inside `width_in`; reserve room
  for an outside legend in the layout.
- `paper.fit_to_width(fig, width_in, pad)` then `paper.save_fig(fig, path,
  pad)` with the same `pad`, for content that legitimately spans the whole
  slot. Call `fit_to_width` before any overlay that measures final geometry.

### A2. Chrome

No top or right spines; axis lines, tick marks and tick labels all in
`paper.AXIS_GREY` (dark enough for text, contrast 5.4 on white); short ticks
(2 pt) with tick labels close to them (1.5 pt pad); no legend frames, no grid unless it carries reading
value (then 0.5 pt). Data lines 0.75 to 1 pt. `apply()` sets all of these;
do not override them per figure.

### A3. Scripts

One script per figure, writing to the path the `.tex` includes. All
human-facing strings (panel titles, axis labels, legend names and grouping)
sit in one block of constants at the top of the script, so copy is edited in
one place. Run scripts through the project's environment (a pixi task per
figure).

## B. Diagrams (HTML/SVG)

For a schematic matplotlib cannot draw: a method overview, a pipeline, a
data-flow figure. The figure is HTML/SVG on a fixed px canvas, usually
generated by a Python script so computed parts stay consistent with the data,
and exported to a true-size PDF:

```python
paper.html_to_pdf("figures/intro/overview.dc.html", "figures/intro/overview.pdf",
                  canvas_w=1584, canvas_h=704, width_in=paper.LINEWIDTH_IN)
```

- roach depends on `playwright`; the browser is a one-time step per
  environment: `pixi run playwright install chromium`.
- Pick the canvas so 1 pt is a whole number of px (4 px/pt: 1584 px wide for
  a 5.5 in figure) and express every font size in that unit on the type
  scale above (7 pt = 28 px at 4 px/pt); a denser sub-scale is a deviation
  the project's `DESIGN.md` must document. The scale factor is computed from
  `canvas_w` and `width_in`, so any canvas size exports correctly.
- Declare `font-family: 'Inter'` and nothing else: the export injects the
  package's Inter, so the HTML carries no font files or paths. On screen it
  falls back to the system sans; the PDF is what gets reviewed.
- Colors come from `paper.shades` on the role constants, named in one dict
  at the top of the generator; the markup refers to names, never hex.
- Draw each shape as one closed filled outline (an arrow is a single polygon,
  shaft and head together), not as overlapping strokes whose ends are placed
  by hand. Where pieces must overlap, put them in one group carrying the
  opacity and overlap them generously; never let two fills meet exactly at
  an edge, which antialiases into a visible seam.
- The rest of section 0 applies unchanged: role colors, the review loop, PDF
  output at the slot width.

## C. Tables

Build the table body as a string of `&`-separated rows,
`paper.align_tex(body)` to column-align the source, `paper.save_tex(tex,
path)` to write it; the `.tex` `\input`s the body and keeps the caption and
`tabular` preamble. Numbers come from the same code that makes the figures,
never typed by hand. Our method's row or name uses the `\ours` macro.
