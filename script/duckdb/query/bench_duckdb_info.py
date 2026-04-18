#!/usr/bin/env python3
"""
DuckDB 单轮扫描：token 数 + JSON 执行计划节点数 + 算子(含次数)
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import duckdb
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from benchmark_config import (
    get_dataset_conf,
    get_query_params,
    load_benchmark_config,
    render_query_template,
)
from split_query_tokens import split_query_tokens

DB_CONF = dict(db_path='/duckdb_data/mapl.db')
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / 'common' / 'benchmark_config.json'


def _walk_plan(node: dict, cnt: Counter):
    if 'name' in node:
        if node['name'] == 'SEQ_SCAN ' or node['name'] == 'SEQ_SCAN':
            cnt['TABLE_SCAN'] += 1
        else:
            cnt[node['name']] += 1
    for child in node.get('children', []):
        _walk_plan(child, cnt)


def get_tokens_and_nodes(conn: duckdb.DuckDBPyConnection, sql: str):
    tokens = split_query_tokens(sql)
    explain_sql = 'EXPLAIN (FORMAT JSON) \n' + sql
    raw: str = conn.execute(explain_sql).fetchone()[1]
    plan = json.loads(raw)[0]
    counter = Counter()
    _walk_plan(plan, counter)
    node_cnt = sum(counter.values())
    ops = ','.join(f'{op}:{c}' for op, c in counter.most_common())
    return tokens, node_cnt, ops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset', choices=['mapl', 'mapm', 'maps'], default='mapl',
                        help='选择数据集（默认 mapl）')
    parser.add_argument('-c', '--config', type=Path, default=DEFAULT_CONFIG_PATH,
                        help='配置文件路径（默认 script/common/benchmark_config.json）')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+', help='待测 .sql 文件')
    args = parser.parse_args()

    config = load_benchmark_config(args.config)
    dataset_conf = get_dataset_conf(config, 'duckdb', args.dataset)

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files if Path(f).name not in exclude_set], key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    conn = duckdb.connect(dataset_conf['db_path'], config={'allow_unsigned_extensions': 'true'})
    conn.execute('INSTALL duckpgq FROM community; INSTALL vss;')
    conn.execute('LOAD duckpgq; LOAD vss;')
    conn.execute("SET memory_limit='50GB'")

    header = ['file', 'tokens', 'nodes', 'ops']
    rows = []
    for f in file_list:
        sql = render_query_template(
            f.read_text(encoding='utf-8').strip(),
            get_query_params(config, 'duckdb', f.stem, args.dataset),
        )
        tokens, nodes, ops = get_tokens_and_nodes(conn, sql)
        print(f'{f.name}: tokens={len(tokens)}, nodes={nodes}, top3={ops}')
        rows.append([f.name, len(tokens), nodes, ops])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)
    print(f'结果已写入 {args.out}')
    conn.close()


if __name__ == '__main__':
    main()
