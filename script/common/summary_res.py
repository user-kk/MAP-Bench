#!/usr/bin/env python3
"""
多数据库 benchmark 结果纵向合并器
用法：
    python summary_res.py --db duck=duck.csv --db helm=helm.csv -o all.csv
    python summary_res.py --pivot          # 生成 6 个对比表
"""
import pathlib
import argparse
import datetime
from collections import OrderedDict
import pandas as pd
import sys

# ------------------------------------------------------------------
# 1. 默认配置
# ------------------------------------------------------------------
ROOT_PATH = '/home/hyh/OpenAlex_mini_new/'

DEFAULT_DBS = OrderedDict([
    ('gredodb',        ROOT_PATH + 'script/gredodb/query/out/res_2025-12-13_19:47:45.csv'),
    ('arangodb',      ROOT_PATH + 'script/arangodb/query/out/res_2025-12-12_20:00:55.csv'),
    ('agensgraph-sp',    ROOT_PATH + 'script/agensgraph/query/out/res_2025-12-12_19:59:51.csv'),
    ('agensgraph-mp',    ROOT_PATH + 'script/agensgraph/query/out/res_2025-12-13_22:10:16.csv'),
    ('duckdb-st',     ROOT_PATH + 'script/duckdb/query/out/res_2025-12-12_21:09:06.csv'),
    ('duckdb-mt',     ROOT_PATH + 'script/duckdb/query/out/res_2025-12-13_22:09:52.csv'),
    ('polystore',     ROOT_PATH + 'script/polystore/query/out/res_2025-12-12_20:54:33.csv'),
])

# 需要保留的列（纵向合并用）
KEEP_COLS = ['file', 'method', 'latency_ms', 'cpu_time_ms', 
             'cpu_%', 'rss_gb', 'peak_cpu_%', 'avg_cpu_%']

# 需要生成透视表的列
PIVOT_COLS = ['latency_ms', 'cpu_time_ms', 'cpu_%', 
              'rss_gb', 'peak_cpu_%', 'avg_cpu_%']

# 获取脚本所在目录的绝对路径
SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
# 默认在脚本所在目录的 out 文件夹下输出文件结果
OUT_PATH = SCRIPT_DIR / 'out'

# 确保输出目录存在
OUT_PATH.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 参数解析
# ------------------------------------------------------------------
def parse_cli():
    p = argparse.ArgumentParser(description='纵向合并 or 指标对比')
    p.add_argument('-d', '--db', action='append', default=[],
                   help='指定数据库名与路径，格式 名称=路径，可多次使用')
    p.add_argument('-o', '--output', help='输出文件路径；缺省生成 merged_<时间戳>.[csv|md]')
    p.add_argument('-f', '--format', choices=['csv', 'md', 'markdown'], default='csv',
                   help='输出格式：csv（默认）或 markdown')
    p.add_argument('--pivot', action='store_true',
                   help='生成对比表')
    return p.parse_args()

def build_db_map(args) -> "OrderedDict[str, pathlib.Path]":
    db_map = OrderedDict()
    for item in args.db:
        if '=' not in item:
            raise ValueError(f'--db 参数格式错误：{item}，应为 名称=路径')
        name, path = item.split('=', 1)
        db_map[name.strip()] = pathlib.Path(path.strip())
    for name, path in DEFAULT_DBS.items():
        if name not in db_map and pathlib.Path(path).exists():
            db_map[name] = pathlib.Path(path)
    if not db_map:
        raise FileNotFoundError('未找到任何有效 csv，请通过 --db 或 DEFAULT_DBS 指定')
    return db_map

# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
def main():
    args = parse_cli()
    db_map = build_db_map(args)

    # 统一读取
    frames = []
    for db_name, csv_path in db_map.items():
        df = pd.read_csv(csv_path)
        
        # 检查必需的列是否存在
        missing_cols = [col for col in KEEP_COLS if col not in df.columns]
        if missing_cols:
            raise ValueError(f"CSV 文件 '{csv_path}' 缺少必需的列: {missing_cols}")
        
        # 只保留需要的列
        df = df[KEEP_COLS].copy()
        df.insert(0, 'db', db_name)
        df['file'] = df['file'].apply(lambda x: pathlib.Path(x).stem)
        frames.append(df)
    
    big = pd.concat(frames, ignore_index=True)

    if args.pivot:
        # 生成对比表（不包含 method 列）
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for col in PIVOT_COLS:
            # 只使用 file 作为索引，method 不参与透视表
            pivot = big.pivot_table(
                index='file',  # 修改：只保留 file 作为索引
                columns='db', 
                values=col, 
                aggfunc='first'
            ).fillna('-')
            
            out = OUT_PATH / f'{col}_{ts}.csv'  # 保存到 out 目录
            pivot.to_csv(out)
            print(f'已生成对比表: {out.absolute()} ({len(pivot)} 行 × {len(pivot.columns)} 列)')
    else:
        # 纵向合并输出（保留 method 列）
        big = big.sort_values(['file', 'db']).reset_index(drop=True)
        ext = 'md' if args.format in ('md', 'markdown') else 'csv'
        out_path = OUT_PATH / f"merged_{datetime.datetime.now():%Y%m%d_%H%M%S}.{ext}"  # 保存到 out 目录
        
        if args.format in ('md', 'markdown'):
            big.to_markdown(out_path, index=False)
        else:
            big.to_csv(out_path, index=False)
        print(f'已生成 {out_path.absolute()} ({len(big)} 行 × {len(big.columns)} 列)')

if __name__ == '__main__':
    main()