#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
from matplotlib.lines import Line2D as MLine
from pathlib import Path

ROWS = [
    [
        ('Hybrid-Lookup (H)',      ['H1', 'H2', 'H3', 'H4', 'H5']),
        ('Vector-Similarity (V)',  ['V1', 'V2', 'V3', 'V4']),
    ],
    [
        ('Attribute-Aggregation (A)', ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']),
        ('Graph-Traversal (G)',       ['G1', 'G2', 'G3', 'G4']),
    ],
]

SYSTEMS = [
    ('gredodb_ms',        'FleetDB',          '#3A76AF', ''),
    ('arangodb_ms',      'ArangoDB',         '#2D8E4E', ''),
    ('agensgraph-sp_ms', 'AgensGraph (SP)',  '#F4A742', ''),
    ('agensgraph-mp_ms', 'AgensGraph (MP)',  '#D2691E', '//'),
    ('duckdb-st_ms',     'DuckDB (ST)',      '#B388C9', ''),
    ('duckdb-mt_ms',     'DuckDB (MT)',      '#7B2D8E', '//'),
    ('polystore_ms',     'Polyglot',         '#888888', ''),
]

N_SYS = len(SYSTEMS)
GAP_RATIO = 0.15


def ms_fmt(val, _pos):
    if val >= 1e6:
        return f'{val/1e6:.0f}M'
    if val >= 1e3:
        return f'{val/1e3:.0f}K'
    if val >= 1:
        return f'{val:.0f}'
    return f'{val:.1g}'


def _row_units(groups):
    n = sum(len(q) for _, q in groups)
    n += GAP_RATIO * (len(groups) - 1)
    return n


def parse_cell(cell):
    """
    Parse a CSV cell:
      "" or NaN       -> (np.nan, 'missing')
      "123.4"         -> (123.4, 'normal')
      "123.4*"        -> (123.4, 'special')
    """
    if pd.isna(cell):
        return np.nan, 'missing'

    s = str(cell).strip()
    if s == '':
        return np.nan, 'missing'

    if s.endswith('*'):
        try:
            return float(s[:-1]), 'special'
        except ValueError:
            return np.nan, 'missing'

    try:
        return float(s), 'normal'
    except ValueError:
        return np.nan, 'missing'


def draw(df: pd.DataFrame, out: Path, dpi: int):
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 11,
        'axes.titlesize': 13,
        'axes.labelsize': 11,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 11,
        'axes.linewidth': 0.6,
    })

    fig = plt.figure(figsize=(20, 10), facecolor='white')

    row_tops    = [0.82, 0.45]
    row_bottoms = [0.57, 0.20]

    plot_left  = 0.05
    plot_right = 0.97
    full_span  = plot_right - plot_left

    units_per_row = [_row_units(g) for g in ROWS]
    max_units     = max(units_per_row)

    all_info = []

    for row_idx, groups in enumerate(ROWS):
        ratio    = units_per_row[row_idx] / max_units
        row_span = full_span * ratio
        margin   = (full_span - row_span) / 2
        r_left   = plot_left + margin
        r_right  = plot_right - margin

        cols_info    = []
        width_ratios = []
        for g_idx, (_, queries) in enumerate(groups):
            for qname in queries:
                cols_info.append((g_idx, qname))
                width_ratios.append(1)
            if g_idx < len(groups) - 1:
                cols_info.append(None)
                width_ratios.append(GAP_RATIO)

        gs = gridspec.GridSpec(
            1, len(cols_info), figure=fig,
            width_ratios=width_ratios,
            left=r_left, right=r_right,
            top=row_tops[row_idx], bottom=row_bottoms[row_idx],
            wspace=0.30,
        )

        group_axes = {}

        for col_idx, info in enumerate(cols_info):
            if info is None:
                continue

            g_idx, qname = info
            ax = fig.add_subplot(gs[0, col_idx])
            group_axes.setdefault(g_idx, []).append(ax)

            if qname not in df.index:
                ax.set_visible(False)
                continue

            row_data = df.loc[qname]

            vals, statuses, colors, hatches = [], [], [], []
            for col, _lbl, color, hatch in SYSTEMS:
                v, st = parse_cell(row_data.get(col, np.nan))
                vals.append(v)
                statuses.append(st)
                colors.append(color)
                hatches.append(hatch)

            x = np.arange(N_SYS)

            valid_vals = [v for v in vals if not np.isnan(v)]
            if valid_vals:
                vmin, vmax = min(valid_vals), max(valid_vals)
                ax.set_yscale('log')
                ax.set_ylim(vmin / 4, vmax * 6)
            else:
                ax.set_yscale('log')
                ax.set_ylim(1, 10)

            # # draw bars
            # for i in range(N_SYS):
            #     if statuses[i] == 'missing':
            #         continue

            #     if statuses[i] == 'special':
            #         ax.bar(
            #             x[i], vals[i],
            #             width=0.7,
            #             facecolor='white',
            #             edgecolor=colors[i],
            #             linewidth=1.2,
            #             hatch='///',
            #             zorder=3
            #         )
            #         y_star = min(vals[i] * 1.18, ax.get_ylim()[1] / 1.15)
            #         ax.text(
            #             x[i], y_star, '*',
            #             ha='center', va='bottom',
            #             fontsize=10, color=colors[i], fontweight='bold'
            #         )
            #     else:
            #         ax.bar(
            #             x[i], vals[i],
            #             width=0.7,
            #             color=colors[i],
            #             edgecolor='white',
            #             linewidth=0.4,
            #             hatch=hatches[i],
            #             zorder=3
            #         )
            
            # draw bars
            for i in range(N_SYS):
                if statuses[i] == 'missing':
                    continue

                if statuses[i] == 'special':
                    ax.bar(
                        x[i], vals[i],
                        width=0.7,
                        color=colors[i],
                        edgecolor='white',
                        linewidth=0.4,
                        hatch=hatches[i],
                        alpha=0.35,
                        zorder=3
                    )
                    y_star = min(vals[i] * 1.18, ax.get_ylim()[1] / 1.15)
                    ax.text(
                        x[i], y_star, '*',
                        ha='center', va='bottom',
                        fontsize=10, color=colors[i], fontweight='bold'
                    )
                else:
                    ax.bar(
                        x[i], vals[i],
                        width=0.7,
                        color=colors[i],
                        edgecolor='white',
                        linewidth=0.4,
                        hatch=hatches[i],
                        zorder=3
                    )

            ax.yaxis.set_major_locator(mticker.LogLocator(base=10, numticks=8))
            ax.yaxis.set_minor_locator(
                mticker.LogLocator(base=10, subs=np.arange(2, 10) * 0.1, numticks=15)
            )
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(ms_fmt))

            ax.tick_params(axis='y', which='major', labelsize=10)
            ax.tick_params(axis='y', which='minor', length=2)

            ax.set_xticks([])
            ax.set_xlim(-0.6, N_SYS - 0.4)

            ax.set_title(qname, fontsize=13, pad=6)

            ax.grid(axis='y', which='major', alpha=0.22, zorder=0)
            ax.grid(axis='y', which='minor', alpha=0.06, zorder=0)

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            # mark missing values with ×
            for i in range(N_SYS):
                if statuses[i] == 'missing':
                    ax.text(
                        x[i], ax.get_ylim()[0] * 1.8, '×',
                        ha='center', va='bottom',
                        fontsize=9, color='#aaaaaa'
                    )

            if len(group_axes.get(g_idx, [])) == 1:
                ax.set_ylabel('Latency (ms)', fontsize=11)

        all_info.append((groups, group_axes, row_tops[row_idx]))

    fig.canvas.draw()

    for groups, group_axes, row_top in all_info:
        for g_idx, (cat_label, _) in enumerate(groups):
            axes_list = group_axes.get(g_idx, [])
            if not axes_list:
                continue

            pos_first = axes_list[0].get_position()
            pos_last  = axes_list[-1].get_position()

            x_left  = pos_first.x0
            x_right = pos_last.x1
            x_mid   = (x_left + x_right) / 2

            title_y = row_top + 0.065

            fig.text(
                x_mid, title_y, cat_label,
                fontsize=17, fontweight='bold',
                ha='center', va='bottom',
                color='#333333'
            )

            bracket_y  = title_y - 0.006
            tick_y_bot = bracket_y - 0.012

            line_kw = dict(
                transform=fig.transFigure,
                color='#999999',
                linewidth=0.8,
                clip_on=False
            )

            fig.add_artist(MLine([x_left, x_right], [bracket_y, bracket_y], **line_kw))
            fig.add_artist(MLine([x_left, x_left], [bracket_y, tick_y_bot], **line_kw))
            fig.add_artist(MLine([x_right, x_right], [bracket_y, tick_y_bot], **line_kw))

    handles = [
        Patch(facecolor=c, edgecolor='#666666', linewidth=0.5, hatch=h)
        for _, _, c, h in SYSTEMS
    ]
    labels = [lbl for _, lbl, _, _ in SYSTEMS]

    fig.legend(
        handles, labels,
        loc='lower center',
        ncol=N_SYS,
        fontsize=12,
        frameon=True,
        edgecolor='#cccccc',
        fancybox=True,
        bbox_to_anchor=(0.52, 0.14),
        handlelength=1.5,
        handletextpad=0.5,
        columnspacing=1.2
    )

    fig.savefig(
        str(out),
        dpi=dpi,
        bbox_inches='tight',
        facecolor='white',
        edgecolor='none'
    )

    print(f'Saved: {out}')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description='MAP-Bench bar chart')
    parser.add_argument('-i', '--input', type=Path, required=True)
    parser.add_argument('-o', '--output', type=Path, default=Path('benchmark.pdf'))
    parser.add_argument('--dpi', type=int, default=300)
    args = parser.parse_args()

    # 重要：不要强制数值化，让 "123*" 保留为字符串
    df = pd.read_csv(args.input, dtype=str)
    df = df.set_index('file')

    draw(df, args.output, args.dpi)


if __name__ == '__main__':
    main()