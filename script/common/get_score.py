#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算每个类别、每个数据库的对数归一化得分
"""

import pandas as pd
import numpy as np

TIMEOUT = 600*(10**3) # 超时暂时计成600秒


# ---- 1. 读数 ----
df = pd.read_csv('compare_20251101_174630.csv', index_col=0)
df = df.replace('', np.nan)          # 先把空串变成标准 NaN
df = df.fillna(TIMEOUT)              # 再用超时值填充
df = df.astype(float)

# ---- 2. 参考时间 = 两系统最小值（NaN 不参与） ----
t_ref = df.min(axis=1)  # Series, index 与 df 相同

# ---- 3. 对数得分矩阵 ----
# scores 形状与 df 相同；NaN 位置会得到 NaN
scores = np.log10(1 + t_ref.values[:, None]) / np.log10(1 + df.values)

# ---- 4. 类别定义 ----
cats = {
    'H': ['H1', 'H2', 'H3', 'H4', 'H5'],
    'A': ['A1', 'A2', 'A3', 'A4', 'A5', 'A6'],
    'V': ['V1', 'V2', 'V3', 'V4'],
    'G': ['G1', 'G2', 'G3'],
}

# ---- 5. 打印每条查询的对数归一化得分 ----
# 排序后的系统/查询
sys_order = sorted(df.columns)      # 系统按字母
q_order   = sorted(df.index)        # 查询按字母（不需要可删）

print('每条查询对数归一化得分（score = log10(1+Tref)/log10(1+Tsys)）')
print('query'.ljust(6), end='')
for sys in sys_order:
    print(f'{sys:>12}', end='')
print()

for q in q_order:
    print(f'{q:<6}', end='')
    for sys in sys_order:
        sc = scores[df.index.get_loc(q), df.columns.get_loc(sys)]
        print(f'{sc:12.3f}', end='')
    print()

# ---- 6. 再打印类别汇总 ----
print('\n=== 类别平均 ===')
for sys in df.columns:
    print(f'\n{sys}')
    for k, qs in cats.items():
        mask = df.index.isin(qs)
        cat_scores = scores[mask, df.columns.get_loc(sys)]
        avg = cat_scores.mean() if not np.all(np.isnan(cat_scores)) else 0.0
        print(f'  {k}: {avg:.3f}')