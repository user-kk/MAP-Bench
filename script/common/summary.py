#!/usr/bin/env python3
"""
多数据库 benchmark 结果合并器
配置方式（按优先级从高到低）：
1. 命令行：--db 名称=路径
2. 脚本内 DEFAULT_DBS 字典
3. 若以上都没有，则把剩余 positional 参数当成 csv 路径，文件名当数据库名

----------------------------- 使用用例 --------------------------------
用例 1：完全使用脚本里的默认路径
    python3 compare.py
    # 输出：compare_<时间戳>.csv

用例 2：命令行显式指定数据库（推荐）
    python3 compare.py \
        --db helmdb=/home/hyh/helmdb.csv \
        --db duckdb=/home/hyh/duckdb.csv \
        -o compare_hd.csv

用例 3：遗留兼容模式（直接给 csv 文件）
    python3 compare.py /tmp/helmdb.csv /tmp/duckdb.csv
    # 会自动把文件名前缀当数据库名，生成 compare_<时间戳>.csv

用例 4：输出 Markdown 表格
    python3 compare.py \
        --db helmdb=./helmdb.csv \
        --db duckdb=./duckdb.csv \
        -f markdown -o compare.md
    # 生成 compare.md，内容可直接渲染为表格
----------------------------------------------------------------------
"""
import csv
import pathlib
import sys
import argparse
import datetime
from collections import OrderedDict

# -------------------------------------------------
# 1. 默认配置：数据库名 -> csv 路径（可留空）
# -------------------------------------------------
ROOT_PATH = '/home/hyh/OpenAlex_mini_new/'

DEFAULT_DBS = OrderedDict([
    ('helmdb',        ROOT_PATH + 'script/helmdb/query/out/2025-11-15_21:55:30.csv'),
    ('arangodb',      ROOT_PATH + 'script/arangodb/query/out/2025-11-15_21:59:59.csv'),
    ('agensgraph-sp', ROOT_PATH + 'script/agensgraph/query/out/2025-11-15_21:47:22.csv'),
    ('duckdb-st',     ROOT_PATH + 'script/duckdb/query/out/2025-11-15_21:48:32.csv'),
    ('agensgraph-mp',     ROOT_PATH + 'script/agensgraph/query/out/2025-11-16_21:07:00.csv'),
    ('duckdb-mt',     ROOT_PATH + 'script/duckdb/query/out/2025-11-16_21:14:33.csv'),
])

# -------------------------------------------------
# 工具函数
# -------------------------------------------------
def load_median(path: pathlib.Path) -> dict[str, float]:
    """返回 dict: 查询名 -> median_ms(float)"""
    res = {}
    with path.open(newline='') as f:
        for row in csv.DictReader(f):
            file_raw = row['file'].strip()
            name = pathlib.Path(file_raw).stem
            res[name] = float(row['median_ms'])
    return res

# -------------------------------------------------
# 参数解析
# -------------------------------------------------
def parse_cli():
    p = argparse.ArgumentParser(description='合并多份 benchmark csv 为对比表')
    p.add_argument('files', nargs='*', help='遗留兼容：直接给 csv 路径')
    p.add_argument('-d', '--db', action='append', default=[],
                   help='显式指定数据库名与路径，格式 名称=路径，可多次使用')
    p.add_argument('-o', '--output', help='输出文件路径；缺省生成 compare_<时间戳>.[csv|md]')
    p.add_argument('-f', '--format', choices=['csv', 'md', 'markdown'], default='csv',
                   help='输出格式：csv（默认）或 markdown')
    return p.parse_args()

def build_db_map(args) -> "OrderedDict[str, pathlib.Path]":
    """合并三种来源，返回有序字典"""
    db_map = OrderedDict()

    # 1. 命令行 --db
    for item in args.db:
        if '=' not in item:
            print(f'--db 参数格式错误：{item}，应为 名称=路径', file=sys.stderr)
            sys.exit(1)
        name, path = item.split('=', 1)
        db_map[name.strip()] = pathlib.Path(path.strip())

    # 2. 脚本内默认
    for name, path in DEFAULT_DBS.items():
        if name not in db_map and pathlib.Path(path).exists():
            db_map[name] = pathlib.Path(path)

    # 3. positional 遗留兼容
    for p in map(pathlib.Path, args.files):
        if p.exists():
            name = p.stem.split('_')[0]
            db_map.setdefault(name, p)

    if not db_map:
        print('未找到任何有效 csv，请通过 --db 或 DEFAULT_DBS 指定', file=sys.stderr)
        sys.exit(1)
    return db_map

# -------------------------------------------------
# 写入函数
# -------------------------------------------------
def write_csv(db_map, data, all_queries, out_path: pathlib.Path):
    with out_path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['file'] + [f'{name}_ms' for name in db_map])
        for q in all_queries:
            w.writerow([q] + [data[name].get(q, '') for name in db_map])

def write_markdown(db_map, data, all_queries, out_path: pathlib.Path):

    headers = ['query'] + [f'{name}_ms' for name in db_map] + ['note']

    rows = []
    for q in all_queries:
        row = [q] + [str(data[name].get(q, '')) for name in db_map]
        row.append('')          # 备注列先留空，可手动填
        rows.append(row)

    lines = ['| ' + ' | '.join(headers) + ' |']
    lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
    for r in rows:
        lines.append('| ' + ' | '.join(r) + ' |')

    out_path.write_text('\n'.join(lines), encoding='utf-8')

# -------------------------------------------------
# 主流程
# -------------------------------------------------
def main():
    args = parse_cli()
    db_map = build_db_map(args)

    # 根据格式自动补扩展名
    ext = 'md' if args.format in ('md', 'markdown') else 'csv'
    out_path = pathlib.Path(args.output or f"compare_{datetime.datetime.now():%Y%m%d_%H%M%S}.{ext}")

    # 读取数据
    data = {name: load_median(p) for name, p in db_map.items()}
    all_queries = sorted({q for d in data.values() for q in d})

    # 写入
    if args.format in ('md', 'markdown'):
        write_markdown(db_map, data, all_queries, out_path)
    else:
        write_csv(db_map, data, all_queries, out_path)

    print(f'已生成 {out_path.absolute()}')

if __name__ == '__main__':
    main()