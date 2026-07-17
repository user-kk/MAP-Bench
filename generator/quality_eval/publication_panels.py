import os
import pickle
import random
from collections import Counter

from matplotlib import colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerTuple
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import wasserstein_distance

import cross_citation
import cross_topic
import doc_authorship
import doc_metrics
import graph_degree_ccdf
import relation_ccdf
import relation_dist
import vector_lid_kde
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
    save_pdf,
    save_pdf_loose,
    set_paper_style,
    style_axes,
    style_existing_legend,
)

SEED = 20260322
random.seed(SEED)
np.random.seed(SEED)
set_paper_style()

GENERATOR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_OUTPUT_DIR = os.environ.get("MAP_BENCH_EVAL_PANEL_OUTPUT_DIR", os.path.join(GENERATOR_ROOT, "quality_eval", "output", "panel_result"))
SUMMARY_OUTPUT_DIR = os.environ.get("MAP_BENCH_EVAL_SUMMARY_OUTPUT_DIR", os.path.join(GENERATOR_ROOT, "quality_eval", "output", "summary_result"))
SEED_LOG_PATH = os.path.join(SUMMARY_OUTPUT_DIR, "run_seeds.log")
CROSS_SEED_CANDIDATE_PATH = os.path.join(SUMMARY_OUTPUT_DIR, "last_cross_seeds.txt")
OVERVIEW_CACHE_PATH = os.path.join(SUMMARY_OUTPUT_DIR, "overview_payload.pkl")
os.makedirs(PANEL_OUTPUT_DIR, exist_ok=True)
os.makedirs(SUMMARY_OUTPUT_DIR, exist_ok=True)


def record_seed(run_name):
    with open(SEED_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{run_name}\tseed={SEED}\n")


def reseed(offset):
    random.seed(SEED + offset)
    np.random.seed(SEED + offset)


def reseed_value(seed_value):
    random.seed(seed_value)
    np.random.seed(seed_value)


def record_cross_seed_candidates(citation_seed, topic_seed):
    with open(CROSS_SEED_CANDIDATE_PATH, "w", encoding="utf-8") as f:
        f.write(f"citation_cross_seed={citation_seed}\n")
        f.write(f"topic_cross_seed={topic_seed}\n")


def darken(color, factor=0.88):
    rgb = np.array(mcolors.to_rgb(color))
    return tuple(np.clip(rgb * factor, 0.0, 1.0))


CURVE_COLOR_REAL = darken(COLOR_REAL, 0.95)
CURVE_COLOR_GEN = darken(COLOR_GEN, 0.95)
CURVE_COLOR_RAND = darken(COLOR_RAND, 0.93)


def add_metric_label(ax, metric_name, ours, rand, x, y, ha="left", va="top"):
    ax.text(
        x,
        y,
        f"{metric_name}: G={ours:.3f} | R={rand:.3f}",
        transform=ax.transAxes,
        ha=ha,
        va=va,
        fontsize=6.7,
        color="#47525C",
        bbox={
            "boxstyle": "round,pad=0.18",
            "facecolor": "white",
            "edgecolor": "#C8CED6",
            "linewidth": 0.55,
            "alpha": 0.90,
        },
    )


def metric_lookup(metrics_df):
    mapping = {
        "Work Type": "Work Type",
        "Author Citation Count": "Author Impact",
        "Abstract Length": "Abstract Length",
        "Authorship Count": "Authorship Count",
        "Topics per Work": "Topics per Work",
        "Citation Out-Degree": "Citation Out-Degree",
        "Co-authorship Degree": "Co-authorship Degree",
        "Vector LID": "Vector LID",
        "Citation Consistency": "Citation Consistency",
        "Same-Topic Consistency": "Same-Topic Consistency",
    }
    out = {}
    for plot_name, metric_target in mapping.items():
        row = metrics_df.loc[metrics_df["metric_target"] == metric_target].iloc[0]
        out[plot_name] = (row["metric"], float(row["ours"]), float(row["random"]))
    return out


def model_legend_handles(metric_name=None, ours=None, rand=None, include_hatch=True):
    ours_label = "Generated" if ours is None or metric_name is None else f"Generated ({metric_name}={ours:.3f})"
    rand_label = "Random" if rand is None or metric_name is None else f"Random ({metric_name}={rand:.3f})"
    handles = [
        Line2D([0], [0], color=COLOR_REAL, lw=2.0, ls=LINESTYLE_REAL, label="SF=1 (Baseline)"),
        Line2D([0], [0], color=COLOR_GEN, lw=1.85, ls=LINESTYLE_GEN, label=ours_label),
        Line2D([0], [0], color=COLOR_RAND, lw=1.85, ls=LINESTYLE_RAND, label=rand_label),
    ]
    if include_hatch:
        return [
            Patch(facecolor=COLOR_REAL, edgecolor="#333333", linewidth=0.8, hatch="", label="SF=1 (Baseline)"),
            Patch(facecolor=COLOR_GEN, edgecolor="#333333", linewidth=0.8, hatch="////", label=ours_label),
            Patch(facecolor=COLOR_RAND, edgecolor="#333333", linewidth=0.8, hatch="xx", label=rand_label),
        ]
    return handles


def combined_model_legend_handles():
    return [
        (
            Patch(facecolor=COLOR_REAL, edgecolor="#333333", linewidth=0.8, hatch=""),
            Line2D([0], [0], color=CURVE_COLOR_REAL, lw=2.1, ls="-", solid_capstyle="butt"),
        ),
        (
            Patch(facecolor=COLOR_GEN, edgecolor="#333333", linewidth=0.8, hatch="////"),
            Line2D([0], [0], color=CURVE_COLOR_GEN, lw=2.1, ls=(0, (5.6, 5.0)), dash_capstyle="butt"),
        ),
        (
            Patch(facecolor=COLOR_RAND, edgecolor="#333333", linewidth=0.8, hatch="xx"),
            Line2D([0], [0], color=CURVE_COLOR_RAND, lw=2.1, ls=(0, (5.6, 4.6, 1.1, 7.2)), dash_capstyle="butt"),
        ),
    ]


def draw_manual_overview_legend(fig, center_x):
    groups = [
        ("SF=1 (Baseline)", COLOR_REAL, "", CURVE_COLOR_REAL, "solid"),
        ("Generated", COLOR_GEN, "////", CURVE_COLOR_GEN, "double_dash"),
        ("Random", COLOR_RAND, "xx", CURVE_COLOR_RAND, "dash_dot"),
    ]
    y = 0.902
    item_w = 0.165
    gap = 0.022
    total_w = 3 * item_w + 2 * gap
    left = center_x - total_w / 2.0
    box_w = 0.018
    box_h = 0.015
    pad_box_to_line = 0.010
    line_w = 0.028
    pad_line_to_text = 0.010

    for idx, (label, fill_color, hatch, line_color, line_style_kind) in enumerate(groups):
        item_left = left + idx * (item_w + gap)
        rect_x = item_left
        rect = Rectangle(
            (rect_x, y - box_h / 2.0),
            box_w,
            box_h,
            transform=fig.transFigure,
            facecolor=fill_color,
            edgecolor="#333333",
            linewidth=0.8,
            hatch=hatch,
        )
        fig.add_artist(rect)
        line_x0 = rect_x + box_w + pad_box_to_line
        line_x1 = line_x0 + line_w
        if line_style_kind == "solid":
            line = Line2D(
                [line_x0, line_x1],
                [y, y],
                transform=fig.transFigure,
                color=line_color,
                lw=2.1,
                ls="-",
                solid_capstyle="butt",
            )
            fig.add_artist(line)
        elif line_style_kind == "double_dash":
            seg = 0.0105
            gap_dash = 0.0034
            line1 = Line2D(
                [line_x0, line_x0 + seg],
                [y, y],
                transform=fig.transFigure,
                color=line_color,
                lw=2.1,
                ls="-",
                solid_capstyle="butt",
            )
            line2 = Line2D(
                [line_x0 + seg + gap_dash, line_x0 + 2 * seg + gap_dash],
                [y, y],
                transform=fig.transFigure,
                color=line_color,
                lw=2.1,
                ls="-",
                solid_capstyle="butt",
            )
            fig.add_artist(line1)
            fig.add_artist(line2)
        else:
            seg1 = 0.0165
            gap_dash = 0.0039
            seg2 = 0.0042
            line1 = Line2D(
                [line_x0, line_x0 + seg1],
                [y, y],
                transform=fig.transFigure,
                color=line_color,
                lw=2.1,
                ls="-",
                solid_capstyle="butt",
            )
            line2 = Line2D(
                [line_x0 + seg1 + gap_dash, line_x0 + seg1 + gap_dash + seg2],
                [y, y],
                transform=fig.transFigure,
                color=line_color,
                lw=2.1,
                ls="-",
                solid_capstyle="butt",
            )
            fig.add_artist(line1)
            fig.add_artist(line2)
        text_x = line_x1 + pad_line_to_text
        fig.text(
            text_x,
            y,
            label,
            transform=fig.transFigure,
            ha="left",
            va="center",
            fontsize=9.4,
            color="#303842",
        )


def plot_ccdf_panel(ax, real, gen, rand, title, panel_tag):
    xr, yr = get_ccdf(real)
    xg, yg = get_ccdf(gen)
    xrand, yrand = get_ccdf(rand)
    if len(xr):
        ax.plot(xr, yr, lw=1.62, ls=LINESTYLE_REAL, color=CURVE_COLOR_REAL, alpha=1.0)
    if len(xg):
        ax.plot(xg, yg, lw=1.56, ls=LINESTYLE_GEN, color=CURVE_COLOR_GEN, alpha=1.0)
    if len(xrand):
        ax.plot(xrand, yrand, lw=1.56, ls=LINESTYLE_RAND, color=CURVE_COLOR_RAND, alpha=1.0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("")
    clean_title = f"({panel_tag}) {title}" if panel_tag else title
    ax.set_title(clean_title, loc="left", fontsize=8.5, fontweight="bold", pad=3.0)
    style_axes(ax, grid_axis="y", log_grid=False)


def plot_bar_panel(ax, keys, r_probs, g_probs, rand_probs, title, panel_tag, top_n=10):
    display_keys = keys[:top_n]
    display_r = r_probs[:top_n]
    display_g = g_probs[:top_n]
    display_rand = rand_probs[:top_n]
    x = np.arange(len(display_keys))
    width = 0.25
    ax.bar(x - width, display_r, width, **bar_style_kwargs(COLOR_REAL, hatch=""))
    ax.bar(x, display_g, width, **bar_style_kwargs(COLOR_GEN, hatch="////"))
    ax.bar(x + width, display_rand, width, **bar_style_kwargs(COLOR_RAND, hatch="xx"))
    ax.set_xticks(x)
    if title == "Topics per Work":
        ax.set_xticklabels(display_keys, rotation=0, ha="center")
    else:
        ax.set_xticklabels(display_keys, rotation=25, ha="right")
    ax.set_xlabel("")
    clean_title = f"({panel_tag}) {title}" if panel_tag else title
    ax.set_title(clean_title, loc="left", fontsize=8.5, fontweight="bold", pad=3.0)
    style_axes(ax, grid_axis="y", log_grid=False)


def plot_cross_panel(ax, df, title, panel_tag):
    palette = {"SF=1 (Baseline)": COLOR_REAL, "Generated": COLOR_GEN, "Random": COLOR_RAND}
    sns.boxplot(
        x="Model",
        y="Sim",
        hue="Model",
        data=df,
        palette=palette,
        dodge=False,
        width=0.42,
        linewidth=0.92,
        fliersize=0,
        saturation=0.95,
        ax=ax,
        boxprops={"edgecolor": "#333333"},
        medianprops={"color": "#111111", "linewidth": 1.0},
        whiskerprops={"color": "#4A4A4A", "linewidth": 0.86},
        capprops={"color": "#4A4A4A", "linewidth": 0.86},
    )
    sns.stripplot(
        x="Model",
        y="Sim",
        hue="Model",
        data=df,
        palette=palette,
        dodge=False,
        alpha=0.72,
        jitter=0.12,
        size=2.55,
        edgecolor="#1E1E1E",
        linewidth=0.48,
        ax=ax,
    )
    if ax.get_legend() is not None:
        ax.get_legend().remove()
    ax.set_xlabel("")
    ax.set_ylabel("")
    clean_title = f"({panel_tag}) {title}" if panel_tag else title
    ax.set_title(clean_title, loc="left", fontsize=8.5, fontweight="bold", pad=3.0)
    style_axes(ax, grid_axis="y", log_grid=False)


def relation_discrete_data(col_name):
    real_path = os.path.join(relation_dist.REAL_DATA_ROOT, "works.csv")
    real_row_count = relation_dist.get_row_count(real_path)

    def load_data(root, skip_rows=0):
        c = Counter()
        path = os.path.join(root, "works.csv")
        if os.path.exists(path):
            import csv

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i < skip_rows:
                        continue
                    val = row.get(col_name, "").strip()
                    if val:
                        c[val] += 1
        return c

    real_c = load_data(relation_dist.REAL_DATA_ROOT)
    gen_c = load_data(relation_dist.GEN_DATA_ROOT)
    rand_c = load_data(relation_dist.RANDOM_DATA_ROOT, skip_rows=real_row_count)
    keys, r_probs, g_probs, rand_probs = relation_dist.align_and_normalize(real_c, gen_c, rand_c)
    tvd_gen = relation_dist.calculate_tvd(r_probs, g_probs)
    tvd_rand = relation_dist.calculate_tvd(r_probs, rand_probs)
    return keys, r_probs, g_probs, rand_probs, tvd_gen, tvd_rand


def cross_df(values, plot_limit=84, seed=None):
    rng = random.Random(seed) if seed is not None else None
    data = []
    model_names = ["SF=1 (Baseline)", "Generated", "Random"]
    for model_name, series in zip(model_names, values):
        if rng is not None and len(series) > plot_limit:
            picked = rng.sample(list(series), plot_limit)
        else:
            picked = list(series[:plot_limit])
        for p in picked:
            data.append({"Model": model_name, "Sim": p})
    return pd.DataFrame(data)


def build_metric_summary():
    rows = []

    real_wc, real_aw, real_ac = relation_ccdf.load_data_triple(relation_ccdf.REAL_DATA_ROOT)
    gen_wc, gen_aw, gen_ac = relation_ccdf.load_data_triple(relation_ccdf.GEN_DATA_ROOT)
    rand_wc, rand_aw, rand_ac = relation_ccdf.load_data_triple(relation_ccdf.RANDOM_DATA_ROOT)
    ccdf_tasks = [
        ("Work Citations", real_wc, gen_wc, rand_wc),
        ("Author Productivity", real_aw, gen_aw, rand_aw),
        ("Author Impact", real_ac, gen_ac, rand_ac),
    ]
    for name, real, gen, rand in ccdf_tasks:
        rows.append(
            {
                "group": "relation_ccdf",
                "metric_target": name,
                "metric": "Log-WS",
                "ours": wasserstein_distance(np.log1p(real), np.log1p(gen)),
                "random": wasserstein_distance(np.log1p(real), np.log1p(rand)),
                "lower_is_better": True,
            }
        )

    keys, r_probs, g_probs, rand_probs, tvd_gen, tvd_rand = relation_discrete_data("type")
    rows.append({"group": "relation_bar", "metric_target": "Work Type", "metric": "TVD", "ours": tvd_gen, "random": tvd_rand, "lower_is_better": True})
    keys, r_probs, g_probs, rand_probs, tvd_gen, tvd_rand = relation_discrete_data("language")
    rows.append({"group": "relation_bar", "metric_target": "Work Language", "metric": "TVD", "ours": tvd_gen, "random": tvd_rand, "lower_is_better": True})

    real_doc_count = doc_metrics.get_row_count(os.path.join(doc_metrics.REAL_DATA_ROOT, "works_doc.csv"))
    real_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.REAL_DATA_ROOT)
    gen_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.GEN_DATA_ROOT)
    rand_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.RANDOM_DATA_ROOT, skip_rows=real_doc_count)
    rows.append(
        {
            "group": "document",
            "metric_target": "Abstract Length",
            "metric": "Log-WS",
            "ours": wasserstein_distance(np.log1p(real_lens), np.log1p(gen_lens)),
            "random": wasserstein_distance(np.log1p(real_lens), np.log1p(rand_lens)),
            "lower_is_better": True,
        }
    )

    r_auth, r_top = doc_authorship.load_doc_counts(doc_authorship.REAL_DATA_ROOT)
    g_auth, g_top = doc_authorship.load_doc_counts(doc_authorship.GEN_DATA_ROOT)
    rand_auth, rand_top = doc_authorship.load_doc_counts(doc_authorship.RANDOM_DATA_ROOT, skip_rows=real_doc_count)
    rows.append(
        {
            "group": "document",
            "metric_target": "Authorship Count",
            "metric": "Log-WS",
            "ours": wasserstein_distance(np.log1p(r_auth), np.log1p(g_auth)),
            "random": wasserstein_distance(np.log1p(r_auth), np.log1p(rand_auth)),
            "lower_is_better": True,
        }
    )
    rc, gc, randc = Counter(r_top), Counter(g_top), Counter(rand_top)
    topic_keys = sorted([k for k in set(rc.keys()) | set(gc.keys()) | set(randc.keys()) if k > 0])
    rp = np.array([rc.get(k, 0) for k in topic_keys], dtype=float)
    gp = np.array([gc.get(k, 0) for k in topic_keys], dtype=float)
    randp = np.array([randc.get(k, 0) for k in topic_keys], dtype=float)
    rp /= rp.sum()
    gp /= gp.sum()
    randp /= randp.sum()
    rows.append(
        {
            "group": "document",
            "metric_target": "Topics per Work",
            "metric": "TVD",
            "ours": doc_authorship.calc_tvd(rp, gp),
            "random": doc_authorship.calc_tvd(rp, randp),
            "lower_is_better": True,
        }
    )

    for task in graph_degree_ccdf.TASKS:
        real_file = os.path.join(graph_degree_ccdf.REAL_DATA_ROOT, task["file"])
        skip = graph_degree_ccdf.get_row_count(real_file)
        real_deg = graph_degree_ccdf.get_degrees(real_file, task["mode"])
        gen_deg = graph_degree_ccdf.get_degrees(os.path.join(graph_degree_ccdf.GEN_DATA_ROOT, task["file"]), task["mode"])
        rand_deg = graph_degree_ccdf.get_degrees(os.path.join(graph_degree_ccdf.RANDOM_DATA_ROOT, task["file"]), task["mode"], skip_rows=skip)
        rows.append(
            {
                "group": "graph",
                "metric_target": task["label"],
                "metric": "Log-WS",
                "ours": wasserstein_distance(np.log1p(real_deg), np.log1p(gen_deg)),
                "random": wasserstein_distance(np.log1p(real_deg), np.log1p(rand_deg)),
                "lower_is_better": True,
            }
        )

    real_vec_count = vector_lid_kde.get_row_count(os.path.join(vector_lid_kde.REAL_DATA_ROOT, vector_lid_kde.VECTOR_FILE_NAME))
    X_real = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.REAL_DATA_ROOT)
    X_gen = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.GEN_DATA_ROOT)
    X_rand = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    lid_real = vector_lid_kde.compute_lid(X_real)
    lid_gen = vector_lid_kde.compute_lid(X_gen)
    lid_rand = vector_lid_kde.compute_lid(X_rand)
    rows.append(
        {
            "group": "vector",
            "metric_target": "Vector LID",
            "metric": "WS",
            "ours": wasserstein_distance(lid_real, lid_gen),
            "random": wasserstein_distance(lid_real, lid_rand),
            "lower_is_better": True,
        }
    )

    real_vec_count = cross_citation.get_row_count(os.path.join(cross_citation.SF1_DATA_ROOT, "vector", "works_vec.csv"))
    vec_real = cross_citation.load_vectors(cross_citation.SF1_DATA_ROOT)
    vec_gen = cross_citation.load_vectors(cross_citation.GEN_DATA_ROOT)
    vec_rand = cross_citation.load_vectors(cross_citation.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    pos_real = cross_citation.extract_positive_sims(cross_citation.SF1_DATA_ROOT, vec_real)
    pos_gen = cross_citation.extract_positive_sims(cross_citation.GEN_DATA_ROOT, vec_gen)
    pos_rand = cross_citation.extract_positive_sims(cross_citation.RANDOM_DATA_ROOT, vec_rand)
    rows.append(
        {
            "group": "cross",
            "metric_target": "Citation Consistency",
            "metric": "WS",
            "ours": cross_citation.bootstrap_ws(pos_real, pos_gen)[0],
            "random": cross_citation.bootstrap_ws(pos_real, pos_rand)[0],
            "lower_is_better": True,
        }
    )

    real_vec_count = cross_topic.get_row_count(os.path.join(cross_topic.SF1_DATA_ROOT, "vector", "works_vec.csv"))
    vec_real = cross_topic.load_vectors(cross_topic.SF1_DATA_ROOT)
    w2t_real, t2w_real = cross_topic.load_work_topics(cross_topic.SF1_DATA_ROOT, vec_real)
    pos_real = cross_topic.extract_topic_positive_sims(vec_real, w2t_real, t2w_real)
    vec_gen = cross_topic.load_vectors(cross_topic.GEN_DATA_ROOT)
    w2t_gen, t2w_gen = cross_topic.load_work_topics(cross_topic.GEN_DATA_ROOT, vec_gen)
    pos_gen = cross_topic.extract_topic_positive_sims(vec_gen, w2t_gen, t2w_gen)
    vec_rand = cross_topic.load_vectors(cross_topic.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    w2t_rand, t2w_rand = cross_topic.load_work_topics(cross_topic.RANDOM_DATA_ROOT, vec_rand)
    pos_rand = cross_topic.extract_topic_positive_sims(vec_rand, w2t_rand, t2w_rand)
    rows.append(
        {
            "group": "cross",
            "metric_target": "Same-Topic Consistency",
            "metric": "WS",
            "ours": cross_topic.bootstrap_ws(pos_real, pos_gen)[0],
            "random": cross_topic.bootstrap_ws(pos_real, pos_rand)[0],
            "lower_is_better": True,
        }
    )

    df = pd.DataFrame(rows)
    df["winner"] = np.where(df["ours"] < df["random"], "Generated", "Random")
    df["gap"] = df["random"] - df["ours"]
    return df


def render_ccdf_suite(metrics_df):
    real_wc, real_aw, real_ac = relation_ccdf.load_data_triple(relation_ccdf.REAL_DATA_ROOT)
    gen_wc, gen_aw, gen_ac = relation_ccdf.load_data_triple(relation_ccdf.GEN_DATA_ROOT)
    rand_wc, rand_aw, rand_ac = relation_ccdf.load_data_triple(relation_ccdf.RANDOM_DATA_ROOT)

    real_doc_count = doc_metrics.get_row_count(os.path.join(doc_metrics.REAL_DATA_ROOT, "works_doc.csv"))
    real_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.REAL_DATA_ROOT)
    gen_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.GEN_DATA_ROOT)
    rand_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.RANDOM_DATA_ROOT, skip_rows=real_doc_count)
    r_auth, _ = doc_authorship.load_doc_counts(doc_authorship.REAL_DATA_ROOT)
    g_auth, _ = doc_authorship.load_doc_counts(doc_authorship.GEN_DATA_ROOT)
    rand_auth, _ = doc_authorship.load_doc_counts(doc_authorship.RANDOM_DATA_ROOT, skip_rows=real_doc_count)

    ccdf_specs = [
        ("Work Citations", real_wc, gen_wc, rand_wc),
        ("Author Productivity", real_aw, gen_aw, rand_aw),
        ("Author Impact", real_ac, gen_ac, rand_ac),
        ("Abstract Length", real_lens, gen_lens, rand_lens),
        ("Authorship Count", r_auth, g_auth, rand_auth),
    ]
    for task in graph_degree_ccdf.TASKS:
        real_file = os.path.join(graph_degree_ccdf.REAL_DATA_ROOT, task["file"])
        skip = graph_degree_ccdf.get_row_count(real_file)
        real_deg = graph_degree_ccdf.get_degrees(real_file, task["mode"])
        gen_deg = graph_degree_ccdf.get_degrees(os.path.join(graph_degree_ccdf.GEN_DATA_ROOT, task["file"]), task["mode"])
        rand_deg = graph_degree_ccdf.get_degrees(os.path.join(graph_degree_ccdf.RANDOM_DATA_ROOT, task["file"]), task["mode"], skip_rows=skip)
        ccdf_specs.append((task["label"], real_deg, gen_deg, rand_deg))

    fig, axes = plt.subplots(2, 4, figsize=(14.2, 7.2))
    axes = axes.flatten()
    panel_tags = ["a", "b", "c", "d", "e", "f", "g"]
    for idx, (name, real, gen, rand) in enumerate(ccdf_specs):
        plot_ccdf_panel(axes[idx], real, gen, rand, name, panel_tags[idx])
    axes[5].set_ylabel("")
    axes[6].set_ylabel("")
    axes[7].axis("off")
    for ax in axes[:7]:
        ax.set_ylabel("")
    fig.supylabel("CCDF P(X >= x)", x=0.03, fontsize=9.4, fontweight="bold")
    handles = model_legend_handles(include_hatch=False)
    legend = fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.01), ncol=3, frameon=True)
    style_existing_legend(legend)
    fig.suptitle("Long-Tail Distribution Suite", y=1.03, fontsize=10.2, fontweight="bold")
    save_pdf(fig, os.path.join(PANEL_OUTPUT_DIR, "panel_ccdf_suite.pdf"))


def render_bar_suite(metrics_df):
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.9))

    keys, r_probs, g_probs, rand_probs, tvd_gen, tvd_rand = relation_discrete_data("type")
    plot_bar_panel(axes[0], keys, r_probs, g_probs, rand_probs, "Work Type", "a")

    keys, r_probs, g_probs, rand_probs, tvd_gen, tvd_rand = relation_discrete_data("language")
    plot_bar_panel(axes[1], keys, r_probs, g_probs, rand_probs, "Language", "b")

    real_doc_count = doc_metrics.get_row_count(os.path.join(doc_metrics.REAL_DATA_ROOT, "works_doc.csv"))
    _, r_top = doc_authorship.load_doc_counts(doc_authorship.REAL_DATA_ROOT)
    _, g_top = doc_authorship.load_doc_counts(doc_authorship.GEN_DATA_ROOT)
    _, rand_top = doc_authorship.load_doc_counts(doc_authorship.RANDOM_DATA_ROOT, skip_rows=real_doc_count)
    rc, gc, randc = Counter(r_top), Counter(g_top), Counter(rand_top)
    topic_keys = sorted([k for k in set(rc.keys()) | set(gc.keys()) | set(randc.keys()) if k > 0])
    rp = np.array([rc.get(k, 0) for k in topic_keys], dtype=float)
    gp = np.array([gc.get(k, 0) for k in topic_keys], dtype=float)
    randp = np.array([randc.get(k, 0) for k in topic_keys], dtype=float)
    rp /= rp.sum()
    gp /= gp.sum()
    randp /= randp.sum()
    plot_bar_panel(
        axes[2],
        topic_keys,
        rp,
        gp,
        randp,
        "Topics per Work",
        "c",
    )

    for ax in axes:
        ax.set_ylabel("")
    fig.supylabel("Probability", x=0.03, fontsize=9.4, fontweight="bold")
    legend = fig.legend(handles=model_legend_handles(include_hatch=True), loc="upper center", bbox_to_anchor=(0.5, 1.05), ncol=3, frameon=True)
    style_existing_legend(legend)
    fig.suptitle("Categorical Distribution Suite", y=1.08, fontsize=10.2, fontweight="bold")
    save_pdf(fig, os.path.join(PANEL_OUTPUT_DIR, "panel_bar_suite.pdf"))


def render_cross_suite(metrics_df):
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9))

    real_vec_count = cross_citation.get_row_count(os.path.join(cross_citation.SF1_DATA_ROOT, "vector", "works_vec.csv"))
    vec_real = cross_citation.load_vectors(cross_citation.SF1_DATA_ROOT)
    pos_real = cross_citation.extract_positive_sims(cross_citation.SF1_DATA_ROOT, vec_real)
    vec_gen = cross_citation.load_vectors(cross_citation.GEN_DATA_ROOT)
    pos_gen = cross_citation.extract_positive_sims(cross_citation.GEN_DATA_ROOT, vec_gen)
    vec_rand = cross_citation.load_vectors(cross_citation.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    pos_rand = cross_citation.extract_positive_sims(cross_citation.RANDOM_DATA_ROOT, vec_rand)
    plot_cross_panel(axes[0], cross_df((pos_real, pos_gen, pos_rand)), "Citation Consistency", "a")

    real_vec_count = cross_topic.get_row_count(os.path.join(cross_topic.SF1_DATA_ROOT, "vector", "works_vec.csv"))
    vec_real = cross_topic.load_vectors(cross_topic.SF1_DATA_ROOT)
    w2t_real, t2w_real = cross_topic.load_work_topics(cross_topic.SF1_DATA_ROOT, vec_real)
    pos_real = cross_topic.extract_topic_positive_sims(vec_real, w2t_real, t2w_real)
    vec_gen = cross_topic.load_vectors(cross_topic.GEN_DATA_ROOT)
    w2t_gen, t2w_gen = cross_topic.load_work_topics(cross_topic.GEN_DATA_ROOT, vec_gen)
    pos_gen = cross_topic.extract_topic_positive_sims(vec_gen, w2t_gen, t2w_gen)
    vec_rand = cross_topic.load_vectors(cross_topic.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    w2t_rand, t2w_rand = cross_topic.load_work_topics(cross_topic.RANDOM_DATA_ROOT, vec_rand)
    pos_rand = cross_topic.extract_topic_positive_sims(vec_rand, w2t_rand, t2w_rand)
    plot_cross_panel(axes[1], cross_df((pos_real, pos_gen, pos_rand)), "Same-Topic Consistency", "b")

    axes[0].set_xticks([0, 1, 2])
    axes[0].set_xticklabels(["Base", "Gen", "Rand"])
    axes[1].set_xticks([0, 1, 2])
    axes[1].set_xticklabels(["Base", "Gen", "Rand"])
    fig.supylabel("Cosine Similarity", x=0.04, fontsize=9.4, fontweight="bold")
    legend = fig.legend(handles=model_legend_handles(include_hatch=True), loc="upper center", bbox_to_anchor=(0.5, 1.05), ncol=3, frameon=True)
    style_existing_legend(legend)
    fig.suptitle("Cross-Modal Consistency Suite", y=1.08, fontsize=10.2, fontweight="bold")
    save_pdf(fig, os.path.join(PANEL_OUTPUT_DIR, "panel_cross_suite.pdf"))


def render_vector_single(metrics_df):
    real_vec_count = vector_lid_kde.get_row_count(os.path.join(vector_lid_kde.REAL_DATA_ROOT, vector_lid_kde.VECTOR_FILE_NAME))
    X_real = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.REAL_DATA_ROOT)
    X_gen = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.GEN_DATA_ROOT)
    X_rand = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    lid_real = vector_lid_kde.compute_lid(X_real)
    lid_gen = vector_lid_kde.compute_lid(X_gen)
    lid_rand = vector_lid_kde.compute_lid(X_rand)
    w_gen = wasserstein_distance(lid_real, lid_gen)
    w_rand = wasserstein_distance(lid_real, lid_rand)

    fig, ax = plt.subplots(figsize=(5.8, 3.8))
    sns.kdeplot(lid_real, fill=True, color=COLOR_REAL, lw=1.45, alpha=0.18, label=f"SF=1 (Mean={np.mean(lid_real):.1f})", ax=ax)
    sns.kdeplot(lid_gen, fill=True, color=COLOR_GEN, lw=1.4, alpha=0.22, linestyle=LINESTYLE_GEN, label=f"Generated (Mean={np.mean(lid_gen):.1f}, WS={w_gen:.1f})", ax=ax)
    sns.kdeplot(lid_rand, fill=True, color=COLOR_RAND, lw=1.4, alpha=0.14, linestyle=LINESTYLE_RAND, label=f"Random (Mean={np.mean(lid_rand):.1f}, WS={w_rand:.1f})", ax=ax)
    ax.set_xlabel("Local Intrinsic Dimensionality")
    ax.set_ylabel("Density")
    ax.set_title("(a) Vector LID", loc="left", fontsize=8.5, fontweight="bold", pad=3.0)
    style_axes(ax, grid_axis="y", log_grid=False)
    finalize_legend(ax, loc="upper right")
    save_pdf(fig, os.path.join(PANEL_OUTPUT_DIR, "panel_vector_lid.pdf"))


def export_summary_tables(metrics_df):
    csv_path = os.path.join(SUMMARY_OUTPUT_DIR, "metric_summary.csv")
    md_path = os.path.join(SUMMARY_OUTPUT_DIR, "metric_summary.md")
    metrics_df.to_csv(csv_path, index=False)

    display = metrics_df.copy()
    for col in ["ours", "random", "gap"]:
        display[col] = display[col].map(lambda x: f"{x:.4f}")
    md_lines = [
        "# Metric Summary",
        "",
        "| Group | Target | Metric | Ours | Random | Gap | Winner |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in display.itertuples(index=False):
        md_lines.append(f"| {row.group} | {row.metric_target} | {row.metric} | {row.ours} | {row.random} | {row.gap} | {row.winner} |")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")


def setup_master_axis(ax):
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_color("#D7DCE3")
        spine.set_linewidth(0.68)


def draw_empty_panel(ax):
    setup_master_axis(ax)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.plot([0.18, 0.82], [0.18, 0.82], color="#B8BFC8", lw=1.15)
    ax.text(0.5, 0.12, "N/A", ha="center", va="center", fontsize=7.2, color="#8A949E")


def draw_legend_panel(ax):
    setup_master_axis(ax)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Legend", loc="left", fontsize=8.3, fontweight="bold", pad=3.0)

    line_items = [
        ("SF=1 (Baseline)", COLOR_REAL, LINESTYLE_REAL),
        ("Generated", COLOR_GEN, LINESTYLE_GEN),
        ("Random", COLOR_RAND, LINESTYLE_RAND),
    ]
    for idx, (label, color, linestyle) in enumerate(line_items):
        y = 0.78 - idx * 0.2
        ax.plot([0.08, 0.31], [y, y], color=color, lw=1.55, ls=linestyle, solid_capstyle="round")
        ax.text(0.36, y, label, va="center", fontsize=7.1)

    ax.text(0.08, 0.12, "Bars: color + hatch\nLines: color + linestyle", fontsize=7.0, color="#4A5560", va="bottom")


def draw_axis_notes_panel(ax):
    setup_master_axis(ax)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Axis Notes", loc="left", fontsize=8.3, fontweight="bold", pad=3.0)
    notes = [
        "Bar: x = category / count bin, y = probability",
        "CCDF: x = value, y = P(X >= x)",
        "LID: x = local intrinsic dimensionality, y = density",
        "Cross: x = model group, y = cosine similarity",
    ]
    for idx, note in enumerate(notes):
        ax.text(0.08, 0.83 - idx * 0.19, note, fontsize=7.0, color="#39424C", va="center")


def master_plot_ccdf(ax, real, gen, rand, title):
    plot_ccdf_panel(ax, real, gen, rand, title, panel_tag="")
    ax.set_title(f"{title} (CCDF)", loc="left", fontsize=8.3, fontweight="bold", pad=3.0)
    ax.set_xlabel("")
    ax.set_ylabel("")


def master_plot_bar(ax, keys, r_probs, g_probs, rand_probs, title, top_n=10):
    plot_bar_panel(ax, keys, r_probs, g_probs, rand_probs, title, panel_tag="", top_n=top_n)
    ax.set_title(f"{title} (Bar)", loc="left", fontsize=8.3, fontweight="bold", pad=3.0)


def master_plot_cross(ax, df, title):
    plot_cross_panel(ax, df, title, panel_tag="")
    ax.set_title(f"{title} (Box+Strip)", loc="left", fontsize=8.3, fontweight="bold", pad=3.0)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["Base", "Gen", "Rand"])


def master_plot_vector(ax, lid_real, lid_gen, lid_rand):
    setup_master_axis(ax)
    sns.kdeplot(lid_real, fill=True, color=COLOR_REAL, lw=1.68, alpha=0.08, label="SF=1 (Baseline)", ax=ax)
    sns.kdeplot(lid_gen, fill=True, color=COLOR_GEN, lw=1.62, alpha=0.08, linestyle=LINESTYLE_GEN, label="Generated", ax=ax)
    sns.kdeplot(lid_rand, fill=True, color=COLOR_RAND, lw=1.62, alpha=0.08, linestyle=LINESTYLE_RAND, label="Random", ax=ax)
    for line, curve_color in zip(ax.lines[-3:], [CURVE_COLOR_REAL, CURVE_COLOR_GEN, CURVE_COLOR_RAND]):
        line.set_color(curve_color)
    ax.set_title("Vector LID (KDE)", loc="left", fontsize=8.3, fontweight="bold", pad=3.0)
    style_axes(ax, grid_axis="y", log_grid=False)


def add_panel_ids(fig, axes, labels):
    for ax, label in zip(axes, labels):
        pos = ax.get_position()
        y_offset = 0.056 if label == "a" else 0.036
        fig.text(
            pos.x0 + pos.width / 2.0,
            pos.y0 - y_offset,
            f"({label})",
            ha="center",
            va="top",
            fontsize=7.9,
            fontweight="bold",
            color="#3C4652",
        )


def save_overview_payload(payload):
    with open(OVERVIEW_CACHE_PATH, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_overview_payload():
    if not os.path.exists(OVERVIEW_CACHE_PATH):
        return None
    with open(OVERVIEW_CACHE_PATH, "rb") as f:
        return pickle.load(f)


def build_overview_payload(metrics_df):
    metrics_map = metric_lookup(metrics_df)
    keys, r_probs, g_probs, rand_probs, _, _ = relation_discrete_data("type")
    real_wc, real_aw, real_ac = relation_ccdf.load_data_triple(relation_ccdf.REAL_DATA_ROOT)
    gen_wc, gen_aw, gen_ac = relation_ccdf.load_data_triple(relation_ccdf.GEN_DATA_ROOT)
    rand_wc, rand_aw, rand_ac = relation_ccdf.load_data_triple(relation_ccdf.RANDOM_DATA_ROOT)

    real_doc_count = doc_metrics.get_row_count(os.path.join(doc_metrics.REAL_DATA_ROOT, "works_doc.csv"))
    real_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.REAL_DATA_ROOT)
    gen_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.GEN_DATA_ROOT)
    rand_lens, _ = doc_metrics.load_doc_data_reservoir(doc_metrics.RANDOM_DATA_ROOT, skip_rows=real_doc_count)
    r_auth, r_top = doc_authorship.load_doc_counts(doc_authorship.REAL_DATA_ROOT)
    g_auth, g_top = doc_authorship.load_doc_counts(doc_authorship.GEN_DATA_ROOT)
    rand_auth, rand_top = doc_authorship.load_doc_counts(doc_authorship.RANDOM_DATA_ROOT, skip_rows=real_doc_count)
    rc, gc, randc = Counter(r_top), Counter(g_top), Counter(rand_top)
    topic_keys = sorted([k for k in set(rc.keys()) | set(gc.keys()) | set(randc.keys()) if k > 0])
    rp = np.array([rc.get(k, 0) for k in topic_keys], dtype=float)
    gp = np.array([gc.get(k, 0) for k in topic_keys], dtype=float)
    randp = np.array([randc.get(k, 0) for k in topic_keys], dtype=float)
    rp /= rp.sum()
    gp /= gp.sum()
    randp /= randp.sum()

    graph_specs = []
    for task in graph_degree_ccdf.TASKS:
        real_file = os.path.join(graph_degree_ccdf.REAL_DATA_ROOT, task["file"])
        skip = graph_degree_ccdf.get_row_count(real_file)
        graph_specs.append(
            (
                task["label"],
                graph_degree_ccdf.get_degrees(real_file, task["mode"]),
                graph_degree_ccdf.get_degrees(os.path.join(graph_degree_ccdf.GEN_DATA_ROOT, task["file"]), task["mode"]),
                graph_degree_ccdf.get_degrees(os.path.join(graph_degree_ccdf.RANDOM_DATA_ROOT, task["file"]), task["mode"], skip_rows=skip),
            )
        )

    real_vec_count = vector_lid_kde.get_row_count(os.path.join(vector_lid_kde.REAL_DATA_ROOT, vector_lid_kde.VECTOR_FILE_NAME))
    X_real = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.REAL_DATA_ROOT)
    X_gen = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.GEN_DATA_ROOT)
    X_rand = vector_lid_kde.load_vectors_reservoir(vector_lid_kde.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    lid_real = vector_lid_kde.compute_lid(X_real)
    lid_gen = vector_lid_kde.compute_lid(X_gen)
    lid_rand = vector_lid_kde.compute_lid(X_rand)

    reseed(101)
    real_vec_count = cross_citation.get_row_count(os.path.join(cross_citation.SF1_DATA_ROOT, "vector", "works_vec.csv"))
    vec_real = cross_citation.load_vectors(cross_citation.SF1_DATA_ROOT)
    pos_real_c = cross_citation.extract_positive_sims(cross_citation.SF1_DATA_ROOT, vec_real)
    vec_gen = cross_citation.load_vectors(cross_citation.GEN_DATA_ROOT)
    pos_gen_c = cross_citation.extract_positive_sims(cross_citation.GEN_DATA_ROOT, vec_gen)
    vec_rand = cross_citation.load_vectors(cross_citation.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    pos_rand_c = cross_citation.extract_positive_sims(cross_citation.RANDOM_DATA_ROOT, vec_rand)

    reseed(102)
    real_vec_count = cross_topic.get_row_count(os.path.join(cross_topic.SF1_DATA_ROOT, "vector", "works_vec.csv"))
    vec_real = cross_topic.load_vectors(cross_topic.SF1_DATA_ROOT)
    w2t_real, t2w_real = cross_topic.load_work_topics(cross_topic.SF1_DATA_ROOT, vec_real)
    pos_real_t = cross_topic.extract_topic_positive_sims(vec_real, w2t_real, t2w_real)
    vec_gen = cross_topic.load_vectors(cross_topic.GEN_DATA_ROOT)
    w2t_gen, t2w_gen = cross_topic.load_work_topics(cross_topic.GEN_DATA_ROOT, vec_gen)
    pos_gen_t = cross_topic.extract_topic_positive_sims(vec_gen, w2t_gen, t2w_gen)
    vec_rand = cross_topic.load_vectors(cross_topic.RANDOM_DATA_ROOT, skip_rows=real_vec_count)
    w2t_rand, t2w_rand = cross_topic.load_work_topics(cross_topic.RANDOM_DATA_ROOT, vec_rand)
    pos_rand_t = cross_topic.extract_topic_positive_sims(vec_rand, w2t_rand, t2w_rand)
    payload = {
        "metrics_map": metrics_map,
        "relation_bar": {"keys": keys, "real": r_probs, "gen": g_probs, "rand": rand_probs},
        "author_citation": {"real": real_ac, "gen": gen_ac, "rand": rand_ac},
        "abstract_length": {"real": real_lens, "gen": gen_lens, "rand": rand_lens},
        "authorship_count": {"real": r_auth, "gen": g_auth, "rand": rand_auth},
        "topics_per_work": {"keys": topic_keys, "real": rp, "gen": gp, "rand": randp},
        "graph_specs": graph_specs,
        "vector_lid": {"real": lid_real, "gen": lid_gen, "rand": lid_rand},
        "cross_citation_values": (pos_real_c, pos_gen_c, pos_rand_c),
        "cross_topic_values": (pos_real_t, pos_gen_t, pos_rand_t),
    }
    save_overview_payload(payload)
    return payload


def render_master_overview(metrics_df=None, citation_display_seed=None, topic_display_seed=None, use_cache=True):
    record_seed("panel_master_overview")
    payload = load_overview_payload() if use_cache else None
    if payload is None:
        if metrics_df is None:
            metrics_df = pd.read_csv(os.path.join(SUMMARY_OUTPUT_DIR, "metric_summary.csv"))
        payload = build_overview_payload(metrics_df)

    fig, axes = plt.subplots(
        2,
        5,
        figsize=(15.0, 6.3),
        gridspec_kw={"wspace": 0.24, "hspace": 0.34},
    )
    fig.subplots_adjust(left=0.055, right=0.995, top=0.845, bottom=0.09, wspace=0.19, hspace=0.28)
    center_x = axes[0, 2].get_position().x0 + axes[0, 2].get_position().width / 2.0
    metrics_map = payload["metrics_map"]
    metric_pos = {
        "Work Type": (0.97, 0.96, "right", "top"),
        "Author Citation Count": (0.03, 0.09, "left", "bottom"),
        "Abstract Length": (0.03, 0.09, "left", "bottom"),
        "Authorship Count": (0.03, 0.09, "left", "bottom"),
        "Topics per Work": (0.03, 0.96, "left", "top"),
        "Citation Out-Degree": (0.03, 0.09, "left", "bottom"),
        "Co-authorship Degree": (0.03, 0.09, "left", "bottom"),
        "Vector LID": (0.97, 0.96, "right", "top"),
        "Citation Consistency": (0.97, 0.96, "right", "top"),
        "Same-Topic Consistency": (0.97, 0.96, "right", "top"),
    }

    rel = payload["relation_bar"]
    master_plot_bar(axes[0, 0], rel["keys"], rel["real"], rel["gen"], rel["rand"], "Work Type", top_n=8)
    add_metric_label(axes[0, 0], *metrics_map["Work Type"], *metric_pos["Work Type"])
    ac = payload["author_citation"]
    master_plot_ccdf(axes[0, 1], ac["real"], ac["gen"], ac["rand"], "Author Citation Count")
    add_metric_label(axes[0, 1], *metrics_map["Author Citation Count"], *metric_pos["Author Citation Count"])
    ab = payload["abstract_length"]
    master_plot_ccdf(axes[0, 2], ab["real"], ab["gen"], ab["rand"], "Abstract Length")
    add_metric_label(axes[0, 2], *metrics_map["Abstract Length"], *metric_pos["Abstract Length"])
    au = payload["authorship_count"]
    master_plot_ccdf(axes[0, 3], au["real"], au["gen"], au["rand"], "Authorship Count")
    add_metric_label(axes[0, 3], *metrics_map["Authorship Count"], *metric_pos["Authorship Count"])
    tpw = payload["topics_per_work"]
    master_plot_bar(axes[0, 4], tpw["keys"], tpw["real"], tpw["gen"], tpw["rand"], "Topics per Work", top_n=8)
    add_metric_label(axes[0, 4], *metrics_map["Topics per Work"], *metric_pos["Topics per Work"])

    graph_specs = payload["graph_specs"]
    master_plot_ccdf(axes[1, 0], graph_specs[0][1], graph_specs[0][2], graph_specs[0][3], graph_specs[0][0])
    master_plot_ccdf(axes[1, 1], graph_specs[1][1], graph_specs[1][2], graph_specs[1][3], graph_specs[1][0])
    add_metric_label(axes[1, 0], *metrics_map["Citation Out-Degree"], *metric_pos["Citation Out-Degree"])
    add_metric_label(axes[1, 1], *metrics_map["Co-authorship Degree"], *metric_pos["Co-authorship Degree"])

    vl = payload["vector_lid"]
    master_plot_vector(axes[1, 2], vl["real"], vl["gen"], vl["rand"])
    add_metric_label(axes[1, 2], *metrics_map["Vector LID"], *metric_pos["Vector LID"])

    sysrand = random.SystemRandom()
    citation_cross_seed = citation_display_seed if citation_display_seed is not None else sysrand.randint(0, 2**31 - 1)
    topic_cross_seed = topic_display_seed if topic_display_seed is not None else sysrand.randint(0, 2**31 - 1)
    record_cross_seed_candidates(citation_cross_seed, topic_cross_seed)
    master_plot_cross(axes[1, 3], cross_df(payload["cross_citation_values"], seed=citation_cross_seed), "Citation Consistency")
    add_metric_label(axes[1, 3], *metrics_map["Citation Consistency"], *metric_pos["Citation Consistency"])
    master_plot_cross(axes[1, 4], cross_df(payload["cross_topic_values"], seed=topic_cross_seed), "Same-Topic Consistency")
    add_metric_label(axes[1, 4], *metrics_map["Same-Topic Consistency"], *metric_pos["Same-Topic Consistency"])

    draw_manual_overview_legend(fig, center_x)

    add_panel_ids(fig, axes.flatten(), list("abcdefghij"))
    save_pdf_loose(fig, os.path.join(PANEL_OUTPUT_DIR, "panel_master_overview.pdf"))


def main():
    metrics_df = build_metric_summary()
    export_summary_tables(metrics_df)
    render_ccdf_suite(metrics_df)
    render_bar_suite(metrics_df)
    render_cross_suite(metrics_df)
    render_vector_single(metrics_df)
    render_master_overview(metrics_df)
    print(f"Saved panel outputs to: {PANEL_OUTPUT_DIR}")
    print(f"Saved metric summary to: {SUMMARY_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
