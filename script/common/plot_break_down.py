#!/usr/bin/env python3
"""
Polystore Breakdown — 双栏论文单栏极限紧凑版（白底最终版）
"""

import argparse
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
from pathlib import Path

SELECTED_QUERIES = ['H1', 'H3', 'H5', 'A1', 'A3', 'V1', 'V2', 'V3', 'G1', 'G2']

# ===== 标准论文配色（无透明）=====
ENGINES = {
    'd':  ('MongoDB',    '#4E79A7', 'white'),   # 原蓝（保留）
    'g':  ('Neo4j',      '#D65F5F', 'white'),   # 红稍微柔一点
    'r':  ('PostgreSQL', '#59A14F', 'white'),   # 绿基本OK
    'v':  ('Milvus',     '#E08A2E', 'white'),   # 橙子降一点亮度（关键）
    'py': ('Middleware', '#9E9E9E', 'white'), # 灰加深一点
}
ENGINE_ORDER = ['d', 'g', 'r', 'v', 'py']


def parse_breakdown(raw):
    result = {}
    for m in re.finditer(r'(\w+):([\d.]+)ms\(([\d.]+)%\)', raw):
        result[m.group(1)] = {'ms': float(m.group(2)), 'pct': float(m.group(3))}
    return result


def draw(df_raw, out, dpi):
    # ===== 白底 =====
    plt.rcParams.update({
        'font.size': 8,
        'axes.linewidth': 0.4,
        'font.family': 'sans-serif',
        'axes.facecolor': 'white',
        'figure.facecolor': 'white',
    })

    # ===== 数据 =====
    data = {}
    for _, row in df_raw.iterrows():
        q = str(row['file']).replace('.py', '')
        if q in SELECTED_QUERIES:
            data[q] = parse_breakdown(row['breakdown'])

    # ===== Y布局（极限压缩）=====
    y_pos, y_lbl = [], []
    sep_ys = []
    y, prev = 0.0, None

    for q in SELECTED_QUERIES:
        if q not in data:
            continue
        cat = q[0]
        if prev and cat != prev:
            sep_ys.append(y - 0.06)
            y += 0.12
        y_pos.append(y)
        y_lbl.append(q)
        prev = cat
        y += 0.42

    n = len(y_pos)
    if n == 0:
        print("No data")
        return

    # ===== 单栏尺寸 =====
    col_width = 3.8
    fig_height = n * 0.2 + 0.25

    fig, ax = plt.subplots(figsize=(col_width, fig_height))

    bh = 0.28  # 条高度

    # ===== 画图 =====
    for i, q in enumerate(y_lbl):
        bd = data[q]
        left = 0.0

        for eng in ENGINE_ORDER:
            if eng not in bd:
                continue

            pct = bd[eng]['pct']
            if pct <= 0:
                continue

            nm, cl, tc = ENGINES[eng]

            ax.barh(
                y_pos[i], pct,
                left=left,
                height=bh,
                color=cl,
                edgecolor='white',
                linewidth=0.5
            )

            cx = left + pct / 2

            # ===== 横向标签 =====
            if pct >= 28:
                label = f'{nm} {pct:.0f}%'
            elif pct >= 14:
                label = f'{pct:.0f}%'
            else:
                label = None

            if label:
                ax.text(
                    cx, y_pos[i], label,
                    ha='center', va='center',
                    fontsize=5.5,
                    fontweight='bold',
                    color=tc
                )

            left += pct

    # ===== 分隔线 =====
    for sy in sep_ys:
        ax.axhline(sy, color='#DDDDDD', lw=0.4)

    # ===== 坐标轴 =====
    ax.set_yticks(y_pos)
    ax.set_yticklabels(y_lbl, fontsize=7)
    ax.invert_yaxis()

    ax.set_xlim(0, 100)

    ax.xaxis.set_major_locator(mticker.MultipleLocator(25))
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f'{v:.0f}%')
    )

    ax.tick_params(axis='x', labelsize=6, pad=1)
    ax.tick_params(axis='y', pad=2, length=0)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#BBBBBB')
    ax.spines['bottom'].set_color('#BBBBBB')

    # ===== 图例（顶部紧贴）=====
    handles = [Patch(facecolor=ENGINES[e][1], edgecolor='none')
               for e in ENGINE_ORDER]
    labels = [ENGINES[e][0] for e in ENGINE_ORDER]

    ax.legend(
        handles, labels,
        loc='lower center',
        bbox_to_anchor=(0.5, 0.97),
        ncol=5,
        fontsize=7,
        frameon=False,
        columnspacing=0.6,
        handlelength=0.8,
        handletextpad=0.25,
        borderpad=0,
    )

    # ===== 保存（极限压缩空白）=====
    fig.savefig(
        out,
        dpi=dpi,
        bbox_inches='tight',
        pad_inches=0.01,
        facecolor='white'
    )

    plt.close(fig)
    print(f"Saved: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', type=Path, required=True)
    ap.add_argument('-o', '--output', type=Path, default=Path('breakdown.pdf'))
    ap.add_argument('--dpi', type=int, default=300)
    args = ap.parse_args()

    draw(pd.read_csv(args.input), args.output, args.dpi)


if __name__ == '__main__':
    main()