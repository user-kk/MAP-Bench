#!/usr/bin/env python3
"""
AgensGraph 单轮扫描：token 数 + JSON 执行计划节点数 + ops 算子(含次数)
用法:
    python3 agens_token_nodes.py sql/*.sql -x exclude.sql -o result.csv
CSV:
    file,tokens,nodes,ops_ops
"""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path
import psycopg
from psycopg.types import TypeInfo
from psycopg.adapt import Loader
import os,sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from common.split_query_tokens import split_query_tokens

DB_CONF = dict(
    dbname='openalex_middle',
    user='agensgraph',
    password='linux123',
    host='127.0.0.1',
    port=5555
)

class TextLoader(Loader):
    def load(self, data):
        return bytes(data).decode('utf-8')

def operators_with_cnt(raw_json_text: str) -> str:
    """
    返回格式  operator:count,operator:count,operator:count
    """
    ops = re.findall(r'"Node Type"\s*:\s*"([^"]+)"', raw_json_text)
    if not ops:
        return ''
    counter = Counter(ops)
    top = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    return ','.join([f'{name}:{cnt}' for name, cnt in top])

def get_tokens_and_nodes(cur, sql: str):
    tokens = split_query_tokens(sql)
    explain_sql = "EXPLAIN (FORMAT JSON, BUFFERS OFF) " + sql
    cur.execute(explain_sql)
    raw: str = cur.fetchone()[0]
    node_cnt = len(re.findall(r'^\s*"Node Type"\s*:', raw, re.M))
    ops = operators_with_cnt(raw)
    return tokens, node_cnt, ops

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+', help='待测 .sql 文件')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files
                        if Path(f).name not in exclude_set],
                       key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    conn = psycopg.connect(**DB_CONF, autocommit=True)
    info = TypeInfo.fetch(conn, 'json')
    conn.adapters.register_loader(info.oid, TextLoader)

    cur = conn.cursor()
    cur.execute("SET graph_path = academic_net")
    cur.execute("SET plan_cache_mode = force_custom_plan")
    cur.execute("SET max_parallel_workers_per_gather = 0")

    header = ['file', 'tokens', 'nodes', 'ops']
    rows = []
    for f in file_list:
        sql = f.read_text().strip()
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