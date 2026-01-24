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
    cur_row_idx = 0
    inserts = [[]]
    for line in tex.split("\n"):
        if "&" not in line:
            inserts[cur_row_idx].append(line)
            continue
        rows.append([cell.strip() for cell in line.split("&")])
        cur_row_idx += 1
        inserts.append([])
    num_cols = max(len(row) for row in rows)
    extra_cols_list = []
    for row in rows:
        extra_cols = 0
        while len(row) < num_cols:
            row.insert(0, "")
            extra_cols += 1
        extra_cols_list.append(extra_cols)
    col_widths = []
    for col_idx in range(num_cols):
        max_width = max(len(row[col_idx]) for row in rows)
        col_widths.append(max_width)
    out_rows = []
    for row_idx, row in enumerate(rows):
        for insert in inserts[row_idx]:
            out_rows.append(insert)
        extra_cols = extra_cols_list[row_idx]
        out_cells = []
        for col_idx, cell in enumerate(row):
            padded_cell = cell.ljust(col_widths[col_idx])
            out_cells.append(padded_cell)
        out_row = "  &  ".join(out_cells)
        out_row = out_row[extra_cols:]
        out_rows.append(out_row)
    for insert in inserts[len(rows)]:
        out_rows.append(insert)
    out_tex = "\n".join(out_rows)
    return out_tex
