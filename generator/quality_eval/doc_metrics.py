import csv
import json
import logging
import os
import random
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
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

REAL_DATA_ROOT = "/home/wzh/openalex_gen/openalex_sf1/document"
GEN_DATA_ROOT = "/home/wzh/openalex_gen/generated_output/sf_2_mode_1/document"
RANDOM_DATA_ROOT = "/home/wzh/openalex_gen/random_gen/output/document"
OUTPUT_DIR = "/home/wzh/openalex_gen/quality_eval/output/document_result"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_SAMPLE_SIZE = 20000


def plot_triple_abstract_ccdf(real_data, gen_data, rand_data, filename):
    print(f"\n{'=' * 15} Abstract Length Distribution {'=' * 15}")
    r_arr, g_arr, rand_arr = np.array(real_data), np.array(gen_data), np.array(rand_data)

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

    ax.set_xlabel("Abstract Length (words)")
    ax.set_ylabel("CCDF P(X >= x)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    style_axes(ax, grid_axis="both", log_grid=True)
    ax.legend(handles=make_line_legend(log_w_gen, log_w_rand), loc="lower left")
    finalize_legend(ax, loc="lower left")

    save_path = os.path.join(OUTPUT_DIR, filename.replace(".png", ".pdf"))
    save_pdf(fig, save_path)
    print(f"Saved: {save_path}")


def load_doc_data_reservoir(root_path, skip_rows=0):
    doc_file = os.path.join(root_path, "works_doc.csv")
    tokenizer = re.compile(r"\w+")
    reservoir = []

    if not os.path.exists(doc_file):
        print(f"[WARN] Not found: {doc_file}")
        return [], Counter()

    try:
        with open(doc_file, "r", encoding="utf-8") as f:
            valid_count = 0
            for i, row in enumerate(csv.DictReader(f)):
                if i < skip_rows:
                    continue
                if valid_count < TARGET_SAMPLE_SIZE:
                    reservoir.append(row)
                else:
                    j = random.randint(0, valid_count)
                    if j < TARGET_SAMPLE_SIZE:
                        reservoir[j] = row
                valid_count += 1
    except Exception as e:
        print(f"[Error] reading file: {e}")
        return [], Counter()

    abstract_lengths, word_counter = [], Counter()
    for row in reservoir:
        try:
            doc_str = row.get("doc", "{}")
            if not doc_str or not isinstance(doc_str, str) or not doc_str.strip():
                continue
            doc_json = json.loads(doc_str)
            abstract = doc_json.get("abstract", "")
            if not abstract:
                continue
            words = tokenizer.findall(abstract.lower())
            if not words:
                continue
            abstract_lengths.append(len(words))
            word_counter.update(words)
        except Exception:
            continue

    return abstract_lengths, word_counter


def main():
    print(">>> Setup Data Boundaries...")
    real_doc_count = get_row_count(os.path.join(REAL_DATA_ROOT, "works_doc.csv"))
    print(f">>> Found {real_doc_count} original docs. Will isolate random data.")

    print(">>> Loading Data...")
    real_lens, real_words = load_doc_data_reservoir(REAL_DATA_ROOT, skip_rows=0)
    gen_lens, gen_words = load_doc_data_reservoir(GEN_DATA_ROOT, skip_rows=0)
    rand_lens, rand_words = load_doc_data_reservoir(RANDOM_DATA_ROOT, skip_rows=real_doc_count)

    if real_lens and gen_lens and rand_lens:
        plot_triple_abstract_ccdf(real_lens, gen_lens, rand_lens, "doc_abstract_len_ccdf.pdf")
    else:
        print("[Error] Missing length data.")


if __name__ == "__main__":
    main()
