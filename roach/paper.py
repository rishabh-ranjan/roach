from importlib.resources import files
from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.transforms import Bbox

LINEWIDTH_IN = 5.5

CARDINAL_RED = "#8C1515"
PALO_ALTO = "#175E54"
COOL_GREY = "#53565A"
BLACK = "#1A1A1A"
WHITE = "#FFFFFF"

OURS = CARDINAL_RED

LABEL_SIZE = 7
TITLE_SIZE = LABEL_SIZE
LEGEND_SIZE = LABEL_SIZE
TICK_SIZE = 6
FINE_SIZE = 5


def apply():
    for ttf in (files("roach") / "fonts").iterdir():
        if ttf.name.endswith(".ttf"):
            font_manager.fontManager.addfont(str(ttf))
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Inter"],
            "mathtext.fontset": "stix",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": LABEL_SIZE,
            "axes.titlesize": TITLE_SIZE,
            "axes.titleweight": "normal",
            "axes.labelsize": LABEL_SIZE,
            "xtick.labelsize": TICK_SIZE,
            "ytick.labelsize": TICK_SIZE,
            "legend.fontsize": LEGEND_SIZE,
            "legend.frameon": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.6,
            "grid.linewidth": 0.5,
            "lines.linewidth": 1.0,
        }
    )


def save_at_width(fig, path, width_in=LINEWIDTH_IN, pad=0.06):
    fig.set_figwidth(width_in)
    fig.canvas.draw()
    tight = fig.get_tightbbox(fig.canvas.get_renderer())
    x0 = min(0.0, tight.x0)
    crop = Bbox([[x0, tight.y0 - pad], [x0 + width_in, tight.y1 + pad]])
    Path(path).parent.mkdir(exist_ok=True, parents=True)
    fig.savefig(path, bbox_inches=crop)
    print(f"saved at {path}")


def fit_to_width(fig, width_in=LINEWIDTH_IN, pad=0.02, iters=6):
    target = width_in - 2 * pad
    for _ in range(iters):
        fig.canvas.draw()
        cur = fig.get_tightbbox(fig.canvas.get_renderer()).width
        if abs(cur - target) < 1e-3:
            break
        fig.set_size_inches(fig.get_size_inches() * (target / cur))


def save_fig(fig, path, pad=0.02):
    Path(path).parent.mkdir(exist_ok=True, parents=True)
    fig.savefig(path, bbox_inches="tight", pad_inches=pad)
    print(f"saved at {path}")


def save_tex(tex, path):
    Path(path).parent.mkdir(exist_ok=True, parents=True)
    with open(path, "w") as f:
        f.write(tex)
    print(f"saved at {path}")


def align_tex(tex):
    rows = []
    for line in tex.split("\n"):
        cells = []
        for cell in line.split("&"):
            cells.append(cell.strip())
        rows.append(cells)

    col_widths = []
    for col_idx in range(len(rows[0])):
        col_width = max(len(row[col_idx]) for row in rows)
        col_widths.append(col_width)

    out_rows = []
    for row in rows:
        out_cells = []
        for col_idx, cell in enumerate(row):
            out_cell = cell.rjust(col_widths[col_idx])
            out_cells.append(out_cell)
        out_row = "  &  ".join(out_cells)
        out_rows.append(out_row)
    out_tex = "\n".join(out_rows)

    return out_tex
