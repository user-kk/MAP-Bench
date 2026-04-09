#!/usr/bin/env python3
"""
计算冷/热查询加速比（cold/hot），并按系统×类别输出几何平均数。

用法:
    python3 calc_speedup.py                          # 使用脚本内默认路径
    python3 calc_speedup.py -c cold.csv -w warm.csv  # 命令行覆盖
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path

# =====================================================================
# ★ 默认输入输出路径（可被命令行参数覆盖）
COLD_CSV   = Path('/home/hyh/OpenAlex_mini_new/script/common/out/latency_ms_20260326_162216.csv')
WARM_CSV   = Path('/home/hyh/OpenAlex_mini_new/script/common/out/compare_20260323_162518.csv')
OUTPUT_CSV = Path('speedup.csv')
# =====================================================================

# ★ 冷查询 CSV 列名 → 热查询 CSV 列名 的映射
SYSTEM_MAP = {
    'agensgraph-mp': 'agensgraph-mp_ms',
    'arangodb':      'arangodb_ms',
    'duckdb-mt':     'duckdb-mt_ms',
    'helmdb':        'helmdb_ms',
    'polystore':     'polystore_ms',
}


def load_and_align(cold_path, warm_path):
    """加载冷热 CSV，对齐查询名和系统名，返回逐查询加速比 DataFrame。"""
    cold = pd.read_csv(cold_path).set_index('file')
    warm = pd.read_csv(warm_path).set_index('file')

    cold.index = cold.index.str.strip()
    warm.index = warm.index.str.strip()

    common_queries = sorted(set(cold.index) & set(warm.index))

    records = []
    for q in common_queries:
        cat = q[0]
        for cold_col, warm_col in SYSTEM_MAP.items():
            if cold_col not in cold.columns or warm_col not in warm.columns:
                continue

            c_val = cold.loc[q, cold_col]
            w_val = warm.loc[q, warm_col]

            try:
                c_val = float(str(c_val).strip().replace('-', ''))
            except ValueError:
                continue
            try:
                w_val = float(str(w_val).strip().replace('-', ''))
            except ValueError:
                continue

            if pd.isna(c_val) or pd.isna(w_val) or c_val == 0 or w_val == 0:
                continue

            speedup = c_val / w_val
            records.append({
                'query': q,
                'category': cat,
                'system': cold_col,
                'cold_ms': c_val,
                'warm_ms': w_val,
                'speedup': speedup,
            })

    return pd.DataFrame(records)

def geometric_mean(arr):
    """计算几何平均数（数值稳定版）"""
    arr = np.array(arr, dtype=float)
    arr = arr[arr > 0]  # 过滤非正数（避免 log 问题）

    if len(arr) == 0:
        return np.nan

    return np.exp(np.mean(np.log(arr)))

def compute_geo_means(df):
    """按 (system, category) 分组计算加速比的几何平均数。"""
    grouped = df.groupby(['system', 'category'])['speedup'].apply(
        lambda x: geometric_mean(x.values) if len(x) > 0 else np.nan
    ).reset_index()
    grouped.columns = ['system', 'category', 'geo_mean_speedup']

    all_geo = df.groupby('system')['speedup'].apply(
        lambda x: geometric_mean(x.values) if len(x) > 0 else np.nan
    ).reset_index()
    all_geo.columns = ['system', 'geo_mean_speedup']
    all_geo['category'] = 'ALL'

    combined = pd.concat([grouped, all_geo], ignore_index=True)

    pivot = combined.pivot(index='system', columns='category', values='geo_mean_speedup')

    cat_order = [c for c in ['H', 'A', 'V', 'G', 'ALL'] if c in pivot.columns]
    pivot = pivot[cat_order]
    pivot = pivot.round(2)

    return pivot


def main():
    ap = argparse.ArgumentParser(description='Cold/Warm speedup geometric mean')
    ap.add_argument('-c', '--cold',   type=Path, default=COLD_CSV,   help=f'冷查询 CSV (默认: {COLD_CSV})')
    ap.add_argument('-w', '--warm',   type=Path, default=WARM_CSV,   help=f'热查询 CSV (默认: {WARM_CSV})')
    ap.add_argument('-o', '--output', type=Path, default=OUTPUT_CSV, help=f'输出 CSV   (默认: {OUTPUT_CSV})')
    args = ap.parse_args()

    print(f'Cold:   {args.cold}')
    print(f'Warm:   {args.warm}')
    print(f'Output: {args.output}')
    print()

    df = load_and_align(args.cold, args.warm)

    print('=== Per-Query Speedup (cold / warm) ===')
    detail = df[['query', 'system', 'cold_ms', 'warm_ms', 'speedup']].copy()
    detail['speedup'] = detail['speedup'].round(2)
    print(detail.to_string(index=False))
    print()

    pivot = compute_geo_means(df)
    print('=== Geometric Mean Speedup by System × Category ===')
    print(pivot.to_string())
    print()

    pivot.to_csv(args.output)
    print(f'Saved: {args.output}')


if __name__ == '__main__':
    main()