#!/usr/bin/env python
"""
ArangoDB AQL 性能基准脚本（每单次结果立即落盘 + 实时中位数）
用法:  python bench_arangodb.py q4.aql q5.aql …  [-n 10] [-o result.csv] [-x exclude1.aql exclude2.aql] [-d mapm]
CSV 格式: file,median_ms,run1_ms,run2_ms,…,runN_ms
依赖:  pip install python-arango
"""
import argparse
import csv
import statistics
import sys
import time
from pathlib import Path
from arango import ArangoClient
from arango.http import DefaultHTTPClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from benchmark_config import (
    get_dataset_conf,
    get_query_params,
    load_benchmark_config,
    render_query_template,
)


class MyHTTP(DefaultHTTPClient):
    REQUEST_TIMEOUT = 3600 * 6
    request_timeout = 3600 * 6


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / 'common' / 'benchmark_config.json'
client = ArangoClient(hosts='http://127.0.0.1:8529', http_client=MyHTTP())
db = None


def run_one(aql: str) -> float:
    """端到端计时(ms)"""
    t0 = time.perf_counter()
    cursor = db.aql.execute(
        aql, bind_vars={}, memory_limit=500 * 1024 ** 3,
        profile=False,
        cache=False,
        batch_size=None,
        stream=False,
    )
    _ = [doc for doc in cursor]
    t1 = time.perf_counter()
    return (t1 - t0) * 1000


def flush_csv(out: Path, data: dict, runs: int):
    header = ['file', 'median_ms'] + [f'run{i}_ms' for i in range(1, runs + 1)]
    rows = []
    for fname, times in data.items():
        median = statistics.median(times) if times else ''
        rows.append([fname, f'{median:.3f}' if times else ''] +
                    [f'{t:.3f}' for t in times] +
                    [''] * (runs - len(times)))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='每条 AQL 跑几轮（默认 5）')
    parser.add_argument('-d', '--dataset', choices=['mapl', 'mapm', 'maps'], default='mapl',
                        help='选择数据集（默认 mapl）')
    parser.add_argument('-c', '--config', type=Path, default=DEFAULT_CONFIG_PATH,
                        help='配置文件路径（默认 script/common/benchmark_config.json）')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 路径（默认 result.csv）')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .aql 文件（可一次写多个，空格隔开）')
    parser.add_argument('files', nargs='+', help='待测试 .aql 文件')
    args = parser.parse_args()

    config = load_benchmark_config(args.config)
    dataset_conf = get_dataset_conf(config, 'arangodb', args.dataset)

    global db
    db = client.db(dataset_conf['db_name'], username='root', password='linux123')

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files
                    if Path(f).name not in exclude_set],
                   key=lambda p: p.name)

    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    data = {f.name: [] for f in file_list}

    try:
        flush_csv(args.out, data, args.rounds)
        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                aql = render_query_template(
                    f.read_text(encoding='utf-8').strip(),
                    get_query_params(config, 'arangodb', f.stem, args.dataset),
                )
                t = run_one(aql)
                data[f.name].append(t)
                print(f'R{rnd:02d}  {f.name}: {t:.3f} ms')
                flush_csv(args.out, data, args.rounds)
    except Exception as e:
        print(f'\n[ERROR] {e}  ——  已跑结果已实时写入')
        raise
    finally:
        print(f'结果实时写入 {args.out}')


if __name__ == '__main__':
    main()
