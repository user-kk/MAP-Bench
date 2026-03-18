#!/usr/bin/env python3
"""
helmdb 单轮扫描：token 数 + JSON 执行计划节点数 + 算子(含次数)
用法:
    python3 bench_helmdb_yy.py sql/*.sql -x exclude.sql -o result.csv
CSV:
    file,tokens,nodes,top3_ops
"""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path
import psycopg2
import os,sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from common.split_query_tokens import split_query_tokens

DB_CONF = dict(
    dbname='mapl',
    user='hyh',
    password='Linux123',
    host='127.0.0.1',
    port=9999
)

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

def get_tokens_and_nodes(cur, sql: str,name):
    tokens = split_query_tokens(sql)
    explain_sql = "EXPLAIN (FORMAT JSON, BUFFERS OFF) " + sql
    
    # 1. 把输出注册成普通 text，不让 psycopg2 自动 json.loads
    psycopg2.extensions.register_type(
        psycopg2.extensions.new_type((114, 199), 'JSON_TEXT', lambda v, c: v)
    )
    node_cnt = 0
    ops = ''
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

    conn = psycopg2.connect(**DB_CONF)


    cur = conn.cursor()
    cur.execute("SET enable_pbe_optimization = off")

    header = ['file', 'tokens', 'nodes', 'ops']
    rows = []
    for f in file_list:
        sql = f.read_text().strip()
        tokens, nodes, ops = get_tokens_and_nodes(cur, sql, f.name)
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