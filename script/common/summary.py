#!/usr/bin/env python3
"""
多数据库 benchmark 结果合并器
配置方式（按优先级从高到低）：
1. 命令行：--db 名称=路径
2. 脚本内 DEFAULT_DBS 字典
3. 若以上都没有，则把剩余 positional 参数当成 csv 路径，文件名当数据库名
"""
import csv, pathlib, sys, argparse, datetime
from collections import OrderedDict

# -------------------------------------------------
# 1. 默认配置：数据库名 -> csv 路径（可留空）
# -------------------------------------------------

ROOT_PATH = '/home/hyh/OpenAlex_mini_new/'

DEFAULT_DBS = OrderedDict([
    ('agensgraph', ROOT_PATH + 'script/agensgraph/query/out/q1.csv'),
    ('arangodb',   ROOT_PATH + 'script/arangodb/query/out/q.csv'),
])

# -------------------------------------------------
# 工具函数
# -------------------------------------------------

def load_median(path: pathlib.Path):
    """返回 dict: 查询名 -> median_ms"""
    res = {}
    with path.open(newline='') as f:
        for row in csv.DictReader(f):
            file_raw = row['file'].strip()
            name = pathlib.Path(file_raw).stem   # 去掉扩展名
            res[name] = row['median_ms']
    return res

# -------------------------------------------------
# 参数解析
# -------------------------------------------------
def parse_cli():
    p = argparse.ArgumentParser(description='合并多份 benchmark csv 为对比表')
    p.add_argument('files', nargs='*', help='遗留兼容：直接给 csv 路径')
    p.add_argument('-d', '--db', action='append', default=[],
                   help='显式指定数据库名与路径，格式 名称=路径，可多次使用')
    p.add_argument('-o', '--output', help='输出 csv 路径；缺省生成 compare_<时间戳>.csv')
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
            name = p.stem.split('_')[0]  # agensgraph.csv -> agensgraph
            db_map.setdefault(name, p)

    if not db_map:
        print('未找到任何有效 csv，请通过 --db 或 DEFAULT_DBS 指定', file=sys.stderr)
        sys.exit(1)
    return db_map

# -------------------------------------------------
# 主流程
# -------------------------------------------------
def main():
    args = parse_cli()
    db_map = build_db_map(args)
    out_path = pathlib.Path(args.output or f"compare_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv")

    # 读取数据
    data = {name: load_median(p) for name, p in db_map.items()}

    # 所有查询
    all_queries = sorted({q for d in data.values() for q in d})

    with out_path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['file'] + [f'{name}_ms' for name in db_map])
        for q in all_queries:
            w.writerow([q] + [data[name].get(q, '') for name in db_map])

    print(f'已生成 {out_path.absolute()}')

if __name__ == '__main__':
    main()