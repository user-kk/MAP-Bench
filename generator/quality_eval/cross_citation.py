import csv
import json
import logging
import os
import random
import sys

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import wasserstein_distance
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

from paper_style import COLOR_GEN, COLOR_RAND, COLOR_REAL, save_pdf, set_paper_style, style_axes, style_existing_legend

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

set_paper_style()
csv.field_size_limit(sys.maxsize)

GENERATOR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF1_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_REAL_ROOT", os.path.join(GENERATOR_ROOT, "map-s"))
GEN_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_GENERATED_ROOT", os.path.join(GENERATOR_ROOT, "generated_output", "sf_2_mode_1"))
RANDOM_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_RANDOM_ROOT", os.path.join(GENERATOR_ROOT, "random_gen", "output"))
OUTPUT_DIR = os.environ.get("MAP_BENCH_EVAL_CROSS_OUTPUT_DIR", os.path.join(GENERATOR_ROOT, "quality_eval", "output", "cross_result"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_VECTORS = 50000
PAIR_COUNT = 5000
BOOTSTRAP_ROUNDS = 50


def get_row_count(file_path):
    if not os.path.exists(file_path):
        return 0
    with open(file_path, "r", encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


def load_vectors(root_path, skip_rows=0):
    vec_file = os.path.join(root_path, "vector", "works_vec.csv")
    id_vec_map = {}
    if not os.path.exists(vec_file):
        return {}

    print(f" Loading vectors from {os.path.basename(root_path)} (Skipping {skip_rows} rows)...")
    try:
        with open(vec_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            valid_count = 0
            reservoir = []
            for i, row in tqdm(enumerate(reader), desc="Reading Vecs", unit="rows"):
                if i < skip_rows:
                    continue
                if len(row) < 2:
                    continue
                wid, v_str = row[0], row[-1]
                if not wid or not v_str:
                    continue
                if valid_count < MAX_VECTORS:
                    reservoir.append((wid, v_str))
                else:
                    j = random.randint(0, valid_count)
                    if j < MAX_VECTORS:
                        reservoir[j] = (wid, v_str)
                valid_count += 1
            for wid, v_str in reservoir:
                try:
                    id_vec_map[wid] = json.loads(v_str)
                except Exception:
                    continue
    except Exception as e:
        print(f" [Error] {e}")
    return id_vec_map


def extract_positive_sims(root_path, id_vec_map):
    edge_file = os.path.join(root_path, "graph_edges", "works_referenced_works_e.csv")
    if not os.path.exists(edge_file):
        return []

    valid_edges = []
    print(" Scanning edges...")
    try:
        with open(edge_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in tqdm(reader, desc="Edges", unit="edges"):
                if len(row) < 2:
                    continue
                u, v = row[0], row[1]
                if u in id_vec_map and v in id_vec_map:
                    valid_edges.append((u, v))
    except Exception:
        pass

    actual_sample_size = min(PAIR_COUNT, len(valid_edges))
    if actual_sample_size == 0:
        return []

    sampled_edges = random.sample(valid_edges, actual_sample_size)
    pos_sims = []
    print(f" Computing Absolute Positive Sim for {actual_sample_size} edges...")
    for u, v_true in tqdm(sampled_edges, desc="Sim Calc"):
        s_pos = cosine_similarity([id_vec_map[u]], [id_vec_map[v_true]])[0][0]
        pos_sims.append(s_pos)
    return pos_sims


def bootstrap_ws(sims_real, sims_target, rounds=BOOTSTRAP_ROUNDS):
    n_real, n_target = len(sims_real), len(sims_target)
    if n_real == 0 or n_target == 0:
        return 0.0, 0.0
    distances = []
    for _ in range(rounds):
        sample_real = np.random.choice(sims_real, size=n_real, replace=True)
        sample_target = np.random.choice(sims_target, size=n_target, replace=True)
        distances.append(wasserstein_distance(sample_real, sample_target))
    return np.mean(distances), np.std(distances)


def main():
    print(f"\n{'=' * 50}")
    real_vec_file = os.path.join(SF1_DATA_ROOT, "vector", "works_vec.csv")
    real_vec_count = get_row_count(real_vec_file)
    print(f">>> Found {real_vec_count} original vectors.")

    print(f"\n{'=' * 50}\n>>> 1. Processing Real Data (SF=1)")
    vec_real = load_vectors(SF1_DATA_ROOT, skip_rows=0)
    pos_real = extract_positive_sims(SF1_DATA_ROOT, vec_real)

    print(f"\n{'=' * 50}\n>>> 2. Processing Generated Data")
    vec_gen = load_vectors(GEN_DATA_ROOT, skip_rows=0)
    pos_gen = extract_positive_sims(GEN_DATA_ROOT, vec_gen)

    print(f"\n{'=' * 50}\n>>> 3. Processing Random Data")
    vec_rand = load_vectors(RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    pos_rand = extract_positive_sims(RANDOM_DATA_ROOT, vec_rand)

    if not pos_real:
        return

    ws_gen_mean, _ = bootstrap_ws(pos_real, pos_gen)
    ws_rand_mean, _ = bootstrap_ws(pos_real, pos_rand)

    data = []
    plot_limit = 90
    for p in pos_real[:plot_limit]:
        data.append({"Model": "SF=1 (Baseline)", "Sim": p})
    for p in pos_gen[:plot_limit]:
        data.append({"Model": "Generated", "Sim": p})
    for p in pos_rand[:plot_limit]:
        data.append({"Model": "Random", "Sim": p})

    if not data:
        return
    df = pd.DataFrame(data)
    palette = {"SF=1 (Baseline)": COLOR_REAL, "Generated": COLOR_GEN, "Random": COLOR_RAND}
    order = ["SF=1 (Baseline)", "Generated", "Random"]

    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    sns.boxplot(
        x="Model",
        y="Sim",
        hue="Model",
        data=df,
        palette=palette,
        order=order,
        dodge=False,
        width=0.45,
        linewidth=0.95,
        fliersize=0,
        saturation=0.95,
        ax=ax,
        boxprops={"edgecolor": "#333333"},
        medianprops={"color": "#111111", "linewidth": 1.0},
        whiskerprops={"color": "#4A4A4A", "linewidth": 0.9},
        capprops={"color": "#4A4A4A", "linewidth": 0.9},
    )
    sns.stripplot(
        x="Model",
        y="Sim",
        hue="Model",
        data=df,
        palette=palette,
        order=order,
        dodge=False,
        alpha=0.55,
        jitter=0.12,
        size=3.8,
        edgecolor="#1E1E1E",
        linewidth=0.45,
        ax=ax,
    )
    if ax.get_legend() is not None:
        ax.get_legend().remove()

    ax.set_title("Citation Consistency Distribution")
    ax.set_ylabel("Cosine Similarity")
    ax.set_xlabel("")
    style_axes(ax, grid_axis="y", log_grid=False)

    handles = [
        mpatches.Patch(facecolor=COLOR_REAL, edgecolor="#333333", linewidth=0.8, label="SF=1 (Baseline Ref)"),
        mpatches.Patch(facecolor=COLOR_GEN, edgecolor="#333333", linewidth=0.8, label=f"Generated (WS={ws_gen_mean:.3f})"),
        mpatches.Patch(facecolor=COLOR_RAND, edgecolor="#333333", linewidth=0.8, label=f"Random (WS={ws_rand_mean:.3f})"),
    ]
    legend = ax.legend(handles=handles, loc="best", frameon=True)
    style_existing_legend(legend)

    save_path = os.path.join(OUTPUT_DIR, "cross_citation_ws_boxplot_strip.pdf")
    save_pdf(fig, save_path)
    print(f"\n[Plot Saved]: {save_path}")


if __name__ == "__main__":
    main()
