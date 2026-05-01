import os

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import seaborn as sns

COLOR_REAL = "#366092"
COLOR_GEN = "#C85250"
COLOR_RAND = "#E0C04F"

EDGE_DARK = "#2F2F2F"
GRID_MAJOR = "#D5D9DF"
GRID_MINOR = "#EFF2F5"

LINESTYLE_REAL = "-"
LINESTYLE_GEN = (0, (4.2, 2.0))
LINESTYLE_RAND = (0, (6.0, 2.2, 1.5, 2.2))


def set_paper_style():
    sns.set_theme(style="white", context="paper")
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Carlito",
                "Calibri",
                "Arial",
                "Helvetica",
                "Liberation Sans",
                "Noto Sans",
                "DejaVu Sans",
            ],
            "mathtext.fontset": "dejavusans",
            "mathtext.default": "regular",
            "axes.unicode_minus": False,
            "axes.labelsize": 8.8,
            "axes.titlesize": 9.8,
            "axes.titleweight": "bold",
            "axes.labelweight": "normal",
            "xtick.labelsize": 7.6,
            "ytick.labelsize": 7.6,
            "legend.fontsize": 7.6,
            "axes.linewidth": 0.78,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.major.width": 0.75,
            "ytick.major.width": 0.75,
            "xtick.minor.width": 0.55,
            "ytick.minor.width": 0.55,
            "xtick.major.size": 3.4,
            "ytick.major.size": 3.4,
            "xtick.minor.size": 1.9,
            "ytick.minor.size": 1.9,
            "xtick.minor.visible": True,
            "ytick.minor.visible": True,
            "legend.frameon": True,
            "legend.framealpha": 0.95,
            "legend.fancybox": False,
            "legend.edgecolor": "#B6BFCC",
            "legend.borderpad": 0.35,
            "lines.antialiased": True,
            "patch.antialiased": True,
            "text.antialiased": True,
            "figure.dpi": 170,
            "savefig.dpi": 320,
            "savefig.format": "pdf",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def get_row_count(file_path):
    if not os.path.exists(file_path):
        return 0
    with open(file_path, "r", encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


def get_ccdf(data):
    arr = np.asarray(data)
    arr = np.sort(arr[arr > 0])
    if len(arr) == 0:
        return np.array([]), np.array([])
    x_unique, counts = np.unique(arr, return_counts=True)
    survival = np.cumsum(counts[::-1])[::-1] / len(data)
    return x_unique, survival


def style_axes(ax, grid_axis="y", log_grid=False):
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_color(EDGE_DARK)
        spine.set_linewidth(0.78)
    ax.tick_params(which="both", direction="in", color=EDGE_DARK, pad=2)
    if grid_axis:
        ax.grid(True, which="major", axis=grid_axis, color=GRID_MAJOR, linewidth=0.5)
        if log_grid:
            ax.grid(True, which="minor", axis=grid_axis, color=GRID_MINOR, linewidth=0.28, alpha=0.5)
    else:
        ax.grid(False)


def finalize_legend(ax, loc="best", ncol=1):
    legend = ax.get_legend()
    if legend is None:
        legend = ax.legend(loc=loc, ncol=ncol, frameon=True)
    if legend is not None:
        frame = legend.get_frame()
        frame.set_linewidth(0.8)
        frame.set_edgecolor("#B6BFCC")
        frame.set_facecolor("white")
    return legend


def save_pdf(fig, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path)
    plt.close(fig)


def bar_style_kwargs(color, alpha=0.92, hatch=None):
    return {
        "color": color,
        "alpha": alpha,
        "edgecolor": EDGE_DARK,
        "linewidth": 0.45,
        "hatch": hatch,
    }


def make_patch_legend(ws_gen=None, ws_rand=None):
    handles = [Patch(facecolor=COLOR_REAL, edgecolor=EDGE_DARK, linewidth=0.8, label="SF=1 (Baseline)")]
    gen_label = "Generated" if ws_gen is None else f"Generated (WS={ws_gen:.3f})"
    rand_label = "Random" if ws_rand is None else f"Random (WS={ws_rand:.3f})"
    handles.append(Patch(facecolor=COLOR_GEN, edgecolor=EDGE_DARK, linewidth=0.8, label=gen_label))
    handles.append(Patch(facecolor=COLOR_RAND, edgecolor=EDGE_DARK, linewidth=0.8, label=rand_label, hatch="////"))
    return handles


def make_line_legend(log_ws_gen, log_ws_rand):
    return [
        Line2D([0], [0], color=COLOR_REAL, lw=1.6, ls=LINESTYLE_REAL, label="SF=1 (Baseline)"),
        Line2D([0], [0], color=COLOR_GEN, lw=1.45, ls=LINESTYLE_GEN, label=f"Generated (Log-WS={log_ws_gen:.2f})"),
        Line2D([0], [0], color=COLOR_RAND, lw=1.45, ls=LINESTYLE_RAND, label=f"Random (Log-WS={log_ws_rand:.2f})"),
    ]


def style_existing_legend(legend):
    if legend is None:
        return None
    frame = legend.get_frame()
    frame.set_linewidth(0.8)
    frame.set_edgecolor("#B6BFCC")
    frame.set_facecolor("white")
    return legend
