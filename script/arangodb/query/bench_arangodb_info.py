#!/usr/bin/env python3
"""
ArangoDB AQL 单轮扫描：token 数 + 执行计划节点数 + 全部算子(含次数)
用法:
    python3 aql_token_nodes.py query/*.aql -o result.csv
CSV:
    file,tokens,nodes,ops
依赖:
    pip install python-arango
"""
import argparse
import csv
from collections import Counter
from pathlib import Path
from arango import ArangoClient
from arango.http import DefaultHTTPClient
import os,sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from common.split_query_tokens import split_query_tokens

# ---------------- 连接 ----------------
class MyHTTP(DefaultHTTPClient):
    REQUEST_TIMEOUT = 3600 * 6

client = ArangoClient(hosts="http://127.0.0.1:8529", http_client=MyHTTP())
db = client.db("mapl", username="root", password="linux123")


# ---------------- 解析 explain ----------------
def parse_explain(aql: str):
    """
    返回 (节点总数, 'op1:cnt1,op2:cnt2,...')
    """
    res = db.aql.explain(
        aql,
        bind_vars={},
        all_plans=False,
        opt_rules=[]
    )
    nodes = res.get("nodes", [])
    counter = Counter(n.get("type", "Unknown") for n in nodes)
    ops = ",".join(f"{name}:{cnt}" for name, cnt in
                   sorted(counter.items(), key=lambda x: (-x[1], x[0])))
    return len(nodes), ops

# ---------------- 主流程 ----------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--out", type=Path, default=Path("result.csv"))
    parser.add_argument("-x", "--exclude", nargs="*", default=[])
    parser.add_argument("files", nargs="+", help="待测 .aql 文件")
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted(
        [Path(f).resolve() for f in args.files if Path(f).name not in exclude_set],
        key=lambda p: p.name
    )
    if not file_list:
        print("所有文件均被排除，无事可做。")
        return

    header = ["file", "tokens", "nodes", "ops"]
    rows = []
    for f in file_list:
        aql = f.read_text().strip()
        tokens = split_query_tokens(aql)
        nodes, ops = parse_explain(aql)
        print(f"{f.name}: tokens={len(tokens)}, nodes={nodes}")
        rows.append([f.name, len(tokens), nodes, ops])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as cf:
        csv.writer(cf).writerows([header] + rows)
    print(f"结果已写入 {args.out}")

if __name__ == "__main__":
    main()