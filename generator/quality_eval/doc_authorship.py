import csv
import json
import logging
import os
import random
import sys
from collections import Counter

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
    bar_style_kwargs,
    finalize_legend,
    get_ccdf,
    get_row_count,
    make_line_legend,
    save_pdf,
    set_paper_style,
    style_axes,
)

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
os.environ["OPENBLAS_NUM_THREADS"] = "1"
set_paper_style()
csv.field_size_limit(sys.maxsize)

REAL_DATA_ROOT = "/home/wzh/openalex_gen/openalex_sf1/document"
GEN_DATA_ROOT = "/home/wzh/openalex_gen/generated_output/sf_2_mode_1/document"
RANDOM_DATA_ROOT = "/home/wzh/openalex_gen/random_gen/output/document"
OUTPUT_DIR = "/home/wzh/openalex_gen/quality_eval/output/document_result"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_SAMPLE_SIZE = 20000


def calc_tvd(p_probs, q_probs):
    return 0.5 * np.sum(np.abs(np.array(p_probs) - np.array(q_probs)))


def plot_authorship_ccdf(r_data, g_data, rand_data):
    print(f"\n{'=' * 15} Authorship Count (CCDF) {'=' * 15}")
    r_arr, g_arr, rand_arr = np.array(r_data), np.array(g_data), np.array(rand_data)

    w_g = wasserstein_distance(np.log1p(r_arr), np.log1p(g_arr)) if len(g_arr) else np.inf
    w_r = wasserstein_distance(np.log1p(r_arr), np.log1p(rand_arr)) if len(rand_arr) else np.inf
    print(f"Log-WS | Ours: {w_g:.4f} | Rand: {w_r:.4f} | {'✅' if w_g < w_r else '❌'}")

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

    ax.set_xlabel("Authors per Work")
    ax.set_ylabel("CCDF P(X >= x)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    style_axes(ax, grid_axis="both", log_grid=True)
    ax.legend(handles=make_line_legend(w_g, w_r), loc="lower left")
    finalize_legend(ax, loc="lower left")

    save_pdf(fig, os.path.join(OUTPUT_DIR, "doc_authorship_count_ccdf.pdf"))


def plot_topic_bar(r_data, g_data, rand_data):
    print(f"\n{'=' * 15} Topic Count (Bar) {'=' * 15}")
    rc, gc, randc = Counter(r_data), Counter(g_data), Counter(rand_data)
    keys = sorted([k for k in set(rc.keys()) | set(gc.keys()) | set(randc.keys()) if k > 0])

    def to_probs(c):
        arr = np.array([c.get(k, 0) for k in keys])
        return arr / arr.sum() if arr.sum() > 0 else arr

    rp, gp, randp = to_probs(rc), to_probs(gc), to_probs(randc)
    tvd_g = calc_tvd(rp, gp)
    tvd_r = calc_tvd(rp, randp)
    print(f"TVD    | Ours: {tvd_g:.4f} | Rand: {tvd_r:.4f} | {'✅' if tvd_g < tvd_r else '❌'}")

    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    x = np.arange(len(keys))
    w = 0.25
    ax.bar(x, rp, w, label="SF=1 (Baseline)", **bar_style_kwargs(COLOR_REAL))
    ax.bar(x - w, gp, w, label=f"Generated (TVD={tvd_g:.3f})", **bar_style_kwargs(COLOR_GEN))
    ax.bar(x + w, randp, w, label=f"Random (TVD={tvd_r:.3f})", **bar_style_kwargs(COLOR_RAND, hatch="////"))

    ax.set_xlabel("Topics per Work")
    ax.set_ylabel("Probability")
    ax.set_xticks(x)
    ax.set_xticklabels(keys)
    style_axes(ax, grid_axis="y", log_grid=False)
    finalize_legend(ax, loc="upper right")

    save_pdf(fig, os.path.join(OUTPUT_DIR, "doc_topic_count_bar.pdf"))


def load_doc_counts(root_path, skip_rows=0):
    doc_file = os.path.join(root_path, "works_doc.csv")
    if not os.path.exists(doc_file):
        return [], []

    reservoir = []
    print(f" Reading {os.path.basename(root_path)}/works_doc.csv...")
    try:
        with open(doc_file, "r", encoding="utf-8") as f:
            valid_count = 0
            for i, row in enumerate(csv.DictReader(f)):
                if i < skip_rows:
                    continue
                if valid_count < TARGET_SAMPLE_SIZE:
                    reservoir.append(row.get("doc", "{}"))
                else:
                    j = random.randint(0, valid_count)
                    if j < TARGET_SAMPLE_SIZE:
                        reservoir[j] = row.get("doc", "{}")
                valid_count += 1
    except Exception as e:
        print(f" [Error]: {e}")
        return [], []

    auth_counts, topic_counts = [], []
    for doc_str in reservoir:
        if not doc_str or not isinstance(doc_str, str) or not doc_str.strip():
            continue
        try:
            doc_json = json.loads(doc_str)
            auth_counts.append(len(doc_json.get("authorships", [])))
            topic_counts.append(len(doc_json.get("topics", [])))
        except Exception:
            continue

    return auth_counts, topic_counts


def main():
    real_doc_count = get_row_count(os.path.join(REAL_DATA_ROOT, "works_doc.csv"))

    r_auth, r_top = load_doc_counts(REAL_DATA_ROOT, skip_rows=0)
    g_auth, g_top = load_doc_counts(GEN_DATA_ROOT, skip_rows=0)
    rand_auth, rand_top = load_doc_counts(RANDOM_DATA_ROOT, skip_rows=real_doc_count)

    if not r_auth:
        return

    plot_authorship_ccdf(r_auth, g_auth, rand_auth)
    plot_topic_bar(r_top, g_top, rand_top)
    print("\n✅ All Document Structural Metrics Evaluated.")


if __name__ == "__main__":
    main()
