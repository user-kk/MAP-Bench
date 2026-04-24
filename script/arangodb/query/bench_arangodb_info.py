#!/usr/bin/env python3
"""
ArangoDB AQL 单轮扫描：token 数 + 执行计划节点数 + 全部算子(含次数)
用法:
    python bench_arangodb_info.py query/*.aql -o result.csv -d mapm
CSV:
    file,tokens,nodes,ops
依赖:
    pip install python-arango
"""
import argparse
import csv
from collections import Counter
from pathlib import Path
import sys
from arango import ArangoClient
from arango.http import DefaultHTTPClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from benchmark_config import (
    get_dataset_conf,
    get_query_params,
    load_benchmark_config,
    render_query_template,
)
from split_query_tokens import split_query_tokens


class MyHTTP(DefaultHTTPClient):
    REQUEST_TIMEOUT = 3600 * 6


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / 'common' / 'benchmark_config.json'
client = ArangoClient(hosts='http://127.0.0.1:8529', http_client=MyHTTP())
db = None


def parse_explain(aql: str):
    res = db.aql.explain(
        aql,
        bind_vars={},
        all_plans=False,
        opt_rules=[]
    )
    nodes = res.get('nodes', [])
    counter = Counter(n.get('type', 'Unknown') for n in nodes)
    ops = ','.join(
        f'{name}:{cnt}' for name, cnt in sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    )
    return len(nodes), ops


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset', choices=['mapl', 'mapm', 'maps'], default='mapl',
                        help='选择数据集（默认 mapl）')
    parser.add_argument('-c', '--config', type=Path, default=DEFAULT_CONFIG_PATH,
                        help='配置文件路径（默认 script/common/benchmark_config.json）')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+', help='待测 .aql 文件')
    args = parser.parse_args()

    config = load_benchmark_config(args.config)
    dataset_conf = get_dataset_conf(config, 'arangodb', args.dataset)

    global db
    db = client.db(dataset_conf['db_name'], username='root', password='linux123')

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted(
        [Path(f).resolve() for f in args.files if Path(f).name not in exclude_set],
        key=lambda p: p.name
    )
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    header = ['file', 'tokens', 'nodes', 'ops']
    rows = []
    for f in file_list:
        aql = render_query_template(
            f.read_text(encoding='utf-8').strip(),
            get_query_params(config, 'arangodb', f.stem, args.dataset),
        )
        tokens = split_query_tokens(aql)
        nodes, ops = parse_explain(aql)
        print(f'{f.name}: tokens={len(tokens)}, nodes={nodes}, ops={ops}')
        rows.append([f.name, len(tokens), nodes, ops])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)
    print(f'结果已写入 {args.out}')


if __name__ == '__main__':
    main()
