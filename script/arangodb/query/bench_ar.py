#!/usr/bin/env python3
import statistics, csv, json, argparse
from pathlib import Path
from arango import ArangoClient

"""
ArangoDB AQL 性能基准脚本
用法:  python3 bench_ar.py q4.aql q5.aql ...  [-n 5]
输出:  终端实时中位数 + result.csv
依赖:  pip install python-arango
"""

# ---------- 配置 ----------
client = ArangoClient(hosts='http://127.0.0.1:8529')
db   = client.db('openalex_middle', username='root', password='linux123')
# ---------------------------

def run_one(aql: str):
    """返回单次执行时间（毫秒）"""
    cursor = db.aql.execute(
        aql,
        bind_vars={},
        # 500 GB = 500 * 1024^3 字节
        memory_limit=500 * 1024**3,
        profile=True          # 等价于 profile=2
    )
    exec_time_s = cursor.statistics()['execution_time']   # 秒
    exec_time_ms = exec_time_s * 1000                   # 毫秒
    return exec_time_ms

def bench_file(fpath: Path, runs: int):
    aql = fpath.read_text().strip()
    times = [run_one(aql) for _ in range(runs)]
    return times

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--runs', type=int, default=5)
    parser.add_argument('files', nargs='+', help='.aql files')
    args = parser.parse_args()

    rows = []
    for f in map(Path, args.files):
        times = bench_file(f, args.runs)
        median = statistics.median(times)
        rows.append([f.name, median] + times)
        print(f'{f.name}: median {median:.3f} ms  (runs: {" ".join(f"{t:.3f}" for t in times)})')

    with open('result.csv', 'w', newline='') as cf:
        w = csv.writer(cf)
        w.writerow(['file', 'median_ms'] + [f'run{i+1}_ms' for i in range(args.runs)])
        w.writerows(rows)

if __name__ == '__main__':
    main()

# python3 ./bench_ar.py q4.aql q5.aql q6.aql q7.aql q8.aql q12.aql q14.aql q15.aql