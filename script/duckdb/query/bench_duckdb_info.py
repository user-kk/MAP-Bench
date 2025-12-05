#!/usr/bin/env python3
"""
DuckDB 单轮扫描：token 数 + JSON 执行计划节点数 + 算子(含次数)
用法:
    python3 duck_token_nodes.py sql/*.sql -x exclude.sql -o result.csv
CSV:
    file,tokens,nodes,_ops
"""
import argparse
import csv
import re
import json
from collections import Counter
from pathlib import Path
import duckdb
import os,sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from common.split_query_tokens import split_query_tokens

DB_CONF = dict(
    db_path='/duckdb_data/openalex_middle.db'   # 换成自己的库
)

# ---------- 计划解析 ----------
# ---------- 新增：JSON 遍历 ----------
def _walk_plan(node: dict, cnt: Counter):
    """递归遍历 DuckDB JSON 计划，统计节点"""
    if "name" in node:          # DuckDB 用 "name" 字段存放算子名称
        cnt[node["name"]] += 1
    for child in node.get("children", []):
        _walk_plan(child, cnt)

# ---------- 替换掉原来的 get_tokens_and_nodes ----------
def get_tokens_and_nodes(conn: duckdb.DuckDBPyConnection, sql: str):
    # 1. token 数保持原逻辑
    tokens = split_query_tokens(sql)

    # 2. 拿 JSON 计划
    explain_sql = "EXPLAIN (FORMAT JSON) \n" + sql
    raw: str = conn.execute(explain_sql).fetchone()[1]   # 仍然是 str
    plan = json.loads(raw)[0]                          # DuckDB 返回 [{}]

    # 3. 统计节点数 & 算子
    counter = Counter()
    _walk_plan(plan, counter)
    node_cnt = sum(counter.values())
    ops = ','.join(f'{op}:{c}' for op, c in counter.most_common())

    return tokens, node_cnt, ops

# ---------- 主流程 ----------
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

    conn = duckdb.connect(DB_CONF['db_path'], config={'allow_unsigned_extensions': 'true'})
    # 按需加载扩展
    conn.execute("INSTALL duckpgq FROM community; INSTALL vss;")
    conn.execute("LOAD duckpgq; LOAD vss;")
    # conn.execute("SET threads=1")
    conn.execute("SET memory_limit='50GB'")

    header = ['file', 'tokens', 'nodes', 'ops']
    rows = []
    for f in file_list:
        sql = f.read_text().strip()
        tokens, nodes, top3 = get_tokens_and_nodes(conn, sql)
        print(tokens)
        print(f'{f.name}: tokens={len(tokens)}, nodes={nodes}, top3={top3}')
        rows.append([f.name, len(tokens), nodes, top3])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)
    print(f'结果已写入 {args.out}')
    conn.close()

if __name__ == '__main__':
    main()