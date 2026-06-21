import csv
import logging
import os
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

GENERATOR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_REAL_GRAPH_DIR", os.path.join(GENERATOR_ROOT, "map-s", "graph_edges"))
GEN_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_GENERATED_GRAPH_DIR", os.path.join(GENERATOR_ROOT, "generated_output", "sf_2_mode_1", "graph_edges"))
RANDOM_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_RANDOM_GRAPH_DIR", os.path.join(GENERATOR_ROOT, "random_gen", "output", "graph_edges"))
OUTPUT_DIR = os.environ.get("MAP_BENCH_EVAL_GRAPH_OUTPUT_DIR", os.path.join(GENERATOR_ROOT, "quality_eval", "output", "graph_result"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

TASKS = [
    {
        "key": "citation_out",
        "file": "works_referenced_works_e.csv",
        "mode": "out",
        "label": "Citation Out-Degree",
        "filename": "graph_citation_outdegree_ccdf.pdf",
    },
    {
        "key": "coauthor",
        "file": "authors_authors_e.csv",
        "mode": "undirected",
        "label": "Co-authorship Degree",
        "filename": "graph_coauthor_degree_ccdf.pdf",
    },
]


def get_degrees(file_path, mode, skip_rows=0):
    degrees = Counter()
    if not os.path.exists(file_path):
        return []

    print(f" Reading {os.path.basename(file_path)}...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for i, row in enumerate(reader):
                if i < skip_rows:
                    continue
                if len(row) < 2:
                    continue
                u, v = row[0], row[1]
                if mode == "out":
                    degrees[u] += 1
                elif mode == "in":
                    degrees[v] += 1
                elif mode == "undirected":
                    degrees[u] += 1
                    degrees[v] += 1
        return list(degrees.values())
    except Exception as e:
        print(f" [Error]: {e}")
        return []


def analyze_and_plot(real_data, gen_data, rand_data, task):
    print(f"\n{'=' * 15} {task['label']} {'=' * 15}")

    r_arr, g_arr, rand_arr = np.array(real_data), np.array(gen_data), np.array(rand_data)
    if len(r_arr) == 0:
        return

    log_w_gen = wasserstein_distance(np.log1p(r_arr), np.log1p(g_arr)) if len(g_arr) > 0 else np.inf
    log_w_rand = wasserstein_distance(np.log1p(r_arr), np.log1p(rand_arr)) if len(rand_arr) > 0 else np.inf
    print(f"Log-WS | Ours: {log_w_gen:.4f} | Rand: {log_w_rand:.4f} | {'✅' if log_w_gen < log_w_rand else '❌'}")

    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    xr, yr = get_ccdf(r_arr)
    xg, yg = get_ccdf(g_arr)
    xrand, yrand = get_ccdf(rand_arr)

    if len(xr) > 0:
        ax.plot(xr, yr, lw=1.6, ls=LINESTYLE_REAL, color=COLOR_REAL, alpha=0.96, drawstyle="steps-post")
    if len(xg) > 0:
        ax.plot(xg, yg, lw=1.45, ls=LINESTYLE_GEN, color=COLOR_GEN, alpha=0.96, drawstyle="steps-post")
    if len(xrand) > 0:
        ax.plot(xrand, yrand, lw=1.45, ls=LINESTYLE_RAND, color=COLOR_RAND, alpha=0.92, drawstyle="steps-post")

    ax.set_xlabel(task["label"])
    ax.set_ylabel("CCDF P(X >= x)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    style_axes(ax, grid_axis="both", log_grid=True)
    ax.legend(handles=make_line_legend(log_w_gen, log_w_rand), loc="lower left")
    finalize_legend(ax, loc="lower left")

    save_path = os.path.join(OUTPUT_DIR, task["filename"])
    save_pdf(fig, save_path)
    print(f"Saved: {save_path}")


def main():
    for task in TASKS:
        real_file = os.path.join(REAL_DATA_ROOT, task["file"])
        gen_file = os.path.join(GEN_DATA_ROOT, task["file"])
        rand_file = os.path.join(RANDOM_DATA_ROOT, task["file"])

        real_edge_count = get_row_count(real_file)
        print(f">>> Found {real_edge_count} original edges in {task['file']}. Will isolate random edges.")

        real_degrees = get_degrees(real_file, task["mode"], skip_rows=0)
        gen_degrees = get_degrees(gen_file, task["mode"], skip_rows=0)
        rand_degrees = get_degrees(rand_file, task["mode"], skip_rows=real_edge_count)

        analyze_and_plot(real_degrees, gen_degrees, rand_degrees, task)


if __name__ == "__main__":
    main()
