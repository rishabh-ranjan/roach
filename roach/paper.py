import math
from importlib.resources import files
from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.transforms import Bbox

LINEWIDTH_IN = 5.5

CARDINAL_RED = "#8C1515"
PALO_ALTO = "#175E54"
COOL_GREY = "#53565A"
AXIS_GREY = "#7E8083"
BLACK = "#1A1A1A"
WHITE = "#FFFFFF"

PRIMARY = CARDINAL_RED
ACCENT = PALO_ALTO
NEUTRAL = COOL_GREY
OURS = PRIMARY

LIGHT_L, LIGHT_C = 0.72, 0.55
PALE_L, PALE_C = 0.81, 0.42
SOFT_L, SOFT_C = 0.90, 0.28

LABEL_SIZE = 7
TITLE_SIZE = LABEL_SIZE
LEGEND_SIZE = LABEL_SIZE
TICK_SIZE = 6
FINE_SIZE = 5


def _srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklch(h):
    r, g, b = (_srgb_to_lin(int(h[i : i + 2], 16) / 255) for i in (1, 3, 5))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def oklch_to_hex(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    return "#" + "".join(f"{round(255 * min(1, max(0, _lin_to_srgb(c)))):02X}" for c in rgb)


def shades(h):
    L, C, H = hex_to_oklch(h)
    return {
        "base": h.upper(),
        "light": oklch_to_hex(LIGHT_L, LIGHT_C * C, H),
        "pale": oklch_to_hex(PALE_L, PALE_C * C, H),
        "soft": oklch_to_hex(SOFT_L, SOFT_C * C, H),
    }


def luminance(h):
    r, g, b = (_srgb_to_lin(int(h[i : i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def font_dir():
    return Path(str(files("roach") / "fonts"))


def font_face_css():
    css = []
    for ttf in sorted(font_dir().glob("*.ttf")):
        weight = 700 if "Bold" in ttf.stem else 400
        style = "italic" if "Italic" in ttf.stem else "normal"
        css.append(
            f"@font-face {{ font-family: 'Inter'; src: url('{ttf.as_uri()}') format('truetype');"
            f" font-weight: {weight}; font-style: {style}; }}"
        )
    return "\n".join(css)


def html_to_pdf(src, path, canvas_w, canvas_h, width_in=LINEWIDTH_IN):
    from playwright.sync_api import sync_playwright

    scale = width_in * 96 / canvas_w
    Path(path).parent.mkdir(exist_ok=True, parents=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": canvas_w, "height": canvas_h})
        page.goto(Path(src).resolve().as_uri())
        page.add_style_tag(content=font_face_css())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        page.pdf(
            path=str(path),
            width=f"{canvas_w * scale}px",
            height=f"{canvas_h * scale}px",
            scale=scale,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            print_background=True,
        )
        b.close()
    print(f"saved at {path}")


def apply():
    for ttf in font_dir().glob("*.ttf"):
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
            "axes.edgecolor": AXIS_GREY,
            "xtick.color": AXIS_GREY,
            "ytick.color": AXIS_GREY,
            "xtick.labelcolor": "black",
            "ytick.labelcolor": "black",
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
