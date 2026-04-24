#!/usr/bin/env python3
"""
GredoDB 单轮扫描：token 数 + JSON 执行计划节点数 + 算子(含次数)
"""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path
import psycopg2
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from benchmark_config import (
    get_dataset_conf,
    get_query_params,
    load_benchmark_config,
    render_query_template,
)
from split_query_tokens import split_query_tokens

DB_CONF = dict(
    dbname='mapl',
    user='hyh',
    password='Linux123',
    host='127.0.0.1',
    port=9999,
)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / 'common' / 'benchmark_config.json'


def operators_with_cnt(raw_json_text: str) -> str:
    ops = re.findall(r'"Node Type"\s*:\s*"([^"]+)"', raw_json_text)
    if not ops:
        return ''
    counter = Counter(ops)
    top = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    return ','.join([f'{name}:{cnt}' for name, cnt in top])


def get_tokens_and_nodes(cur, sql: str):
    tokens = split_query_tokens(sql)
    explain_sql = 'EXPLAIN (FORMAT JSON, BUFFERS OFF) ' + sql
    psycopg2.extensions.register_type(
        psycopg2.extensions.new_type((114, 199), 'JSON_TEXT', lambda v, c: v)
    )
    cur.execute(explain_sql)
    raw: str = cur.fetchone()[0]
    node_cnt = len(re.findall(r'^\s*"Node Type"\s*:', raw, re.M))
    ops = operators_with_cnt(raw)
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
    dataset_conf = get_dataset_conf(config, 'gredodb', args.dataset)

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files if Path(f).name not in exclude_set], key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    db_conf = DB_CONF.copy()
    db_conf['dbname'] = dataset_conf['db_name']
    conn = psycopg2.connect(**db_conf)
    cur = conn.cursor()
    cur.execute('SET enable_pbe_optimization = off')

    header = ['file', 'tokens', 'nodes', 'ops']
    rows = []
    for f in file_list:
        sql = render_query_template(
            f.read_text(encoding='utf-8').strip(),
            get_query_params(config, 'gredodb', f.stem, args.dataset),
        )
        tokens, nodes, ops = get_tokens_and_nodes(cur, sql)
        print(f'{f.name}: tokens={len(tokens)}, nodes={nodes}, ops={ops}')
        rows.append([f.name, len(tokens), nodes, ops])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)
    print(f'结果已写入 {args.out}')
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
