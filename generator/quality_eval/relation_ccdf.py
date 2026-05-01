import csv
import logging
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import wasserstein_distance

from paper_style import (
    COLOR_GEN,
    COLOR_RAND,
    COLOR_REAL,
    LINESTYLE_GEN,
    LINESTYLE_RAND,
    LINESTYLE_REAL,
    finalize_legend,
    get_ccdf,
    make_line_legend,
    save_pdf,
    set_paper_style,
    style_axes,
)

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
set_paper_style()
csv.field_size_limit(sys.maxsize)

REAL_DATA_ROOT = "/home/wzh/openalex_gen/openalex_sf1/csv-files"
GEN_DATA_ROOT = "/home/wzh/openalex_gen/generated_output/sf_2_mode_1/csv-files"
RANDOM_DATA_ROOT = "/home/wzh/openalex_gen/random_gen/output/csv-files"
OUTPUT_DIR = "/home/wzh/openalex_gen/quality_eval/output/relation_result"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def safe_parse_int(value):
    try:
        return int(float(value))
    except Exception:
        return None


def analyze_and_plot(real_data, gen_data, random_data, label, filename):
    print(f"\n{'=' * 15} {label} {'=' * 15}")
    r_arr, g_arr, rand_arr = np.array(real_data), np.array(gen_data), np.array(random_data)
    if len(r_arr) == 0:
        return

    log_w_gen = wasserstein_distance(np.log1p(r_arr), np.log1p(g_arr)) if len(g_arr) else np.inf
    log_w_rand = wasserstein_distance(np.log1p(r_arr), np.log1p(rand_arr)) if len(rand_arr) else np.inf
    print(f"Log-WS | Ours: {log_w_gen:.4f} | Rand: {log_w_rand:.4f} | {'✅' if log_w_gen < log_w_rand else '❌'}")

    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    xr, yr = get_ccdf(r_arr)
    xg, yg = get_ccdf(g_arr)
    xrand, yrand = get_ccdf(rand_arr)

    if len(xr):
        ax.plot(xr, yr, lw=1.6, ls=LINESTYLE_REAL, color=COLOR_REAL, alpha=0.96, drawstyle="steps-post")
    if len(xg):
        ax.plot(xg, yg, lw=1.45, ls=LINESTYLE_GEN, color=COLOR_GEN, alpha=0.96, drawstyle="steps-post")
    if len(xrand):
        ax.plot(xrand, yrand, lw=1.45, ls=LINESTYLE_RAND, color=COLOR_RAND, alpha=0.92, drawstyle="steps-post")

    ax.set_xlabel(label)
    ax.set_ylabel("CCDF P(X >= x)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    style_axes(ax, grid_axis="both", log_grid=True)
    ax.legend(handles=make_line_legend(log_w_gen, log_w_rand), loc="lower left")
    finalize_legend(ax, loc="lower left")

    save_path = os.path.join(OUTPUT_DIR, filename.replace(".png", ".pdf"))
    save_pdf(fig, save_path)
    print(f"Saved: {save_path}")


def load_data_triple(root_path):
    w_cite, a_works, a_cite = [], [], []
    w_path = os.path.join(root_path, "works.csv")
    a_path = os.path.join(root_path, "authors.csv")

    if os.path.exists(w_path):
        with open(w_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                v = safe_parse_int(row.get("cited_by_count"))
                if v is not None:
                    w_cite.append(v)

    if os.path.exists(a_path):
        with open(a_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                v1 = safe_parse_int(row.get("works_count"))
                v2 = safe_parse_int(row.get("cited_by_count"))
                if v1 is not None:
                    a_works.append(v1)
                if v2 is not None:
                    a_cite.append(v2)

    return w_cite, a_works, a_cite


def main():
    real_wc, real_aw, real_ac = load_data_triple(REAL_DATA_ROOT)
    gen_wc, gen_aw, gen_ac = load_data_triple(GEN_DATA_ROOT)
    rand_wc, rand_aw, rand_ac = load_data_triple(RANDOM_DATA_ROOT)

    tasks = [
        (real_wc, gen_wc, rand_wc, "Work Citations", "relation_work_citation_ccdf.pdf"),
        (real_aw, gen_aw, rand_aw, "Author Productivity", "relation_author_works_ccdf.pdf"),
        (real_ac, gen_ac, rand_ac, "Author Impact", "relation_author_citation_ccdf.pdf"),
    ]
    for r, g, rnd, label, fname in tasks:
        analyze_and_plot(r, g, rnd, label, fname)


if __name__ == "__main__":
    main()
