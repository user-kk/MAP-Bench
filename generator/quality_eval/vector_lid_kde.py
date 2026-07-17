import csv
import json
import logging
import os
import random
import sys

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from scipy.stats import wasserstein_distance
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

from paper_style import (
    COLOR_GEN,
    COLOR_RAND,
    COLOR_REAL,
    finalize_legend,
    get_row_count,
    save_pdf,
    set_paper_style,
    style_axes,
)

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

set_paper_style()
csv.field_size_limit(sys.maxsize)

GENERATOR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_REAL_VECTOR_DIR", os.path.join(GENERATOR_ROOT, "map-s", "vector"))
GEN_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_GENERATED_VECTOR_DIR", os.path.join(GENERATOR_ROOT, "generated_output", "sf_2_mode_1", "vector"))
RANDOM_DATA_ROOT = os.environ.get("MAP_BENCH_EVAL_RANDOM_VECTOR_DIR", os.path.join(GENERATOR_ROOT, "random_gen", "output", "vector"))
OUTPUT_DIR = os.environ.get("MAP_BENCH_EVAL_VECTOR_OUTPUT_DIR", os.path.join(GENERATOR_ROOT, "quality_eval", "output", "vector_result"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

VECTOR_FILE_NAME = "works_vec.csv"
SAMPLE_SIZE = 10000
K_LID = 50


def compute_lid(X):
    if len(X) < K_LID + 1:
        return np.array([])
    X = normalize(X, norm="l2")
    nbrs = NearestNeighbors(n_neighbors=K_LID + 1, algorithm="brute", n_jobs=1).fit(X)
    distances, _ = nbrs.kneighbors(X)

    neighbor_dists = np.maximum(distances[:, 1:], 1e-10)
    r_k = neighbor_dists[:, -1]
    ratios = r_k[:, np.newaxis] / neighbor_dists
    log_sum = np.sum(np.log(ratios), axis=1)
    return (K_LID - 1) / (log_sum + 1e-10)


def plot_triple_lid_kde(real_data, gen_data, rand_data, w_gen, w_rand):
    fig, ax = plt.subplots(figsize=(5.6, 3.6))

    if len(real_data) > 0:
        sns.kdeplot(real_data, fill=True, color=COLOR_REAL, lw=1.45, linestyle="-", alpha=0.18, label=f"SF=1 (Mean={np.mean(real_data):.1f})", ax=ax)
    if len(gen_data) > 0:
        sns.kdeplot(gen_data, fill=True, color=COLOR_GEN, lw=1.4, linestyle=(0, (7.0, 2.8)), alpha=0.22, label=f"Generated (Mean={np.mean(gen_data):.1f}, WS={w_gen:.1f})", ax=ax)
    if len(rand_data) > 0:
        sns.kdeplot(rand_data, fill=True, color=COLOR_RAND, lw=1.4, linestyle="-.", alpha=0.14, label=f"Random (Mean={np.mean(rand_data):.1f}, WS={w_rand:.1f})", ax=ax)

    ax.set_xlabel("Local Intrinsic Dimensionality")
    ax.set_ylabel("Density")
    style_axes(ax, grid_axis="y", log_grid=False)
    finalize_legend(ax, loc="upper right")

    save_path = os.path.join(OUTPUT_DIR, "vec_lid_kde.pdf")
    save_pdf(fig, save_path)
    print(f"Saved: {save_path}")


def load_vectors_reservoir(root_path, skip_rows=0):
    file_path = os.path.join(root_path, VECTOR_FILE_NAME)
    if not os.path.exists(file_path):
        return np.array([])

    print(f" Reading {os.path.basename(root_path)}/{VECTOR_FILE_NAME}...")
    reservoir = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            valid_count = 0
            for i, row in enumerate(csv.DictReader(f)):
                if i < skip_rows:
                    continue
                vec_str = row.get("vec", "[]")
                if valid_count < SAMPLE_SIZE:
                    reservoir.append(vec_str)
                else:
                    j = random.randint(0, valid_count)
                    if j < SAMPLE_SIZE:
                        reservoir[j] = vec_str
                valid_count += 1
    except Exception as e:
        print(f" [Error]: {e}")
        return np.array([])

    vectors = []
    for val in reservoir:
        try:
            v = json.loads(val)
            if isinstance(v, list) and len(v) > 0:
                vectors.append(v)
        except Exception:
            continue
    return np.array(vectors)


def main():
    print(f"\n{'=' * 15} Vector LID {'=' * 15}")

    real_file = os.path.join(REAL_DATA_ROOT, VECTOR_FILE_NAME)
    real_vec_count = get_row_count(real_file)
    print(f">>> Found {real_vec_count} original vectors. Will isolate random data.")

    X_real = load_vectors_reservoir(REAL_DATA_ROOT, skip_rows=0)
    X_gen = load_vectors_reservoir(GEN_DATA_ROOT, skip_rows=0)
    X_rand = load_vectors_reservoir(RANDOM_DATA_ROOT, skip_rows=real_vec_count)

    lid_real = compute_lid(X_real)
    lid_gen = compute_lid(X_gen)
    lid_rand = compute_lid(X_rand)

    if len(lid_real) == 0:
        return

    w_gen = wasserstein_distance(lid_real, lid_gen) if len(lid_gen) > 0 else float("inf")
    w_rand = wasserstein_distance(lid_real, lid_rand) if len(lid_rand) > 0 else float("inf")
    print(f"WS Dist | Ours: {w_gen:.4f} | Rand: {w_rand:.4f} | {'✅' if w_gen < w_rand else '❌'}")

    plot_triple_lid_kde(lid_real, lid_gen, lid_rand, w_gen, w_rand)


if __name__ == "__main__":
    main()
