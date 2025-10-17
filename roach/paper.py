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
