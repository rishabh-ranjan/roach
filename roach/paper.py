from pathlib import Path
from matplotlib import pyplot as plt
import seaborn as sns

# \linewidth in inches for NeurIPS/ICLR papers
LINE = 5.5


def setup_plt():
    sns.set_theme(context="paper", style="whitegrid", font_scale=0.7)
    plt.rcParams["figure.dpi"] = 157
    plt.rcParams["xtick.major.size"] = 0
    plt.rcParams["ytick.major.size"] = 0
    plt.rcParams["figure.constrained_layout.use"] = True


def save_fig(fig, path):
    Path(path).parent.mkdir(exist_ok=True, parents=True)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.01)
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
