import csv
import logging
import os
import sys
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from paper_style import (
    COLOR_GEN,
    COLOR_RAND,
    COLOR_REAL,
    bar_style_kwargs,
    finalize_legend,
    get_row_count,
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


def calculate_tvd(p_probs, q_probs):
    p = np.array(p_probs)
    q = np.array(q_probs)
    return 0.5 * np.sum(np.abs(p - q))


def align_and_normalize(real_counter, gen_counter, random_counter):
    all_keys = set(real_counter.keys()) | set(gen_counter.keys()) | set(random_counter.keys())
    sorted_keys = sorted(all_keys, key=lambda k: real_counter.get(k, 0), reverse=True)

    r_counts = np.array([real_counter.get(k, 0) for k in sorted_keys])
    g_counts = np.array([gen_counter.get(k, 0) for k in sorted_keys])
    rand_counts = np.array([random_counter.get(k, 0) for k in sorted_keys])

    def to_probs(counts):
        return counts / counts.sum() if counts.sum() > 0 else counts

    return sorted_keys, to_probs(r_counts), to_probs(g_counts), to_probs(rand_counts)


def plot_triple_bar(keys, r_probs, g_probs, rand_probs, filename, tvd_gen, tvd_rand, top_n=10):
    display_keys = keys[:top_n]
    display_r = r_probs[:top_n]
    display_g = g_probs[:top_n]
    display_rand = rand_probs[:top_n]

    x = np.arange(len(display_keys))
    width = 0.25

    fig, ax = plt.subplots(figsize=(5.7, 3.7))
    ax.bar(x, display_r, width, label="SF=1 (Baseline)", **bar_style_kwargs(COLOR_REAL))
    ax.bar(x - width, display_g, width, label=f"Generated (TVD={tvd_gen:.3f})", **bar_style_kwargs(COLOR_GEN))
    ax.bar(x + width, display_rand, width, label=f"Random (TVD={tvd_rand:.3f})", **bar_style_kwargs(COLOR_RAND, hatch="////"))

    ax.set_xlabel("Categories")
    ax.set_ylabel("Probability")
    ax.set_xticks(x)
    ax.set_xticklabels(display_keys, rotation=25, ha="right")
    style_axes(ax, grid_axis="y", log_grid=False)
    finalize_legend(ax, loc="upper right")

    save_path = os.path.join(OUTPUT_DIR, filename.replace(".png", ".pdf"))
    save_pdf(fig, save_path)
    print(f"Saved: {save_path}")


def analyze_attribute(col_name, display_name):
    print(f"\n{'=' * 20} Analyzing: {display_name} {'=' * 20}")

    real_path = os.path.join(REAL_DATA_ROOT, "works.csv")
    real_row_count = get_row_count(real_path)

    def load_data(root, skip_rows=0):
        c = Counter()
        path = os.path.join(root, "works.csv")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i < skip_rows:
                        continue
                    val = row.get(col_name, "").strip()
                    if val:
                        c[val] += 1
        return c

    print(" -> Loading Real data...")
    real_c = load_data(REAL_DATA_ROOT, skip_rows=0)

    print(" -> Loading Generated data (Full Evaluation)...")
    gen_c = load_data(GEN_DATA_ROOT, skip_rows=0)

    print(f" -> Loading Random data (Skipping first {real_row_count} rows)...")
    rand_c = load_data(RANDOM_DATA_ROOT, skip_rows=real_row_count)

    if not real_c:
        return

    keys, r_probs, g_probs, rand_probs = align_and_normalize(real_c, gen_c, rand_c)
    tvd_gen = calculate_tvd(r_probs, g_probs)
    tvd_rand = calculate_tvd(r_probs, rand_probs)

    print(f"\n>>> [Metrics Table] {display_name}")
    print(f"{'Metric':<20} | {'Ours (Gen vs Real)':<20} | {'Baseline (Rand vs Real)':<20} | {'Result'}")
    print("-" * 85)
    print(f"{'TVD (Total Var)':<20} | {tvd_gen:.5f} {'(Low)':<13} | {tvd_rand:.5f} {'(High)':<13} | {'✅' if tvd_gen < tvd_rand else '❌'}")
    print("-" * 85)

    plot_triple_bar(keys, r_probs, g_probs, rand_probs, f"relation_{col_name}_dist.pdf", tvd_gen, tvd_rand)


def main():
    analyze_attribute("type", "Work Type")
    analyze_attribute("language", "Work Language")


if __name__ == "__main__":
    main()
