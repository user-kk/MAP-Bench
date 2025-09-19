#!/usr/bin/env python3
import argparse
import csv
import os
import re
import statistics
import psycopg2
from pathlib import Path


"""
openGauss MMSQL 性能基准脚本
用法:  python3 bench_og.py  q4.sql q5.sql  [-n 5]
输出:  终端实时中位数 + result.csv
依赖:  pip install psycopg2-binary
"""

TOTAL_RUNTIME_RE = re.compile(r'Total\s+runtime:\s+(\d+(?:\.\d+)?)\s*ms', re.I)

DB_CONF = dict(
    dbname='openalex_middle',
    user='hyh',
    password='Linux123',
    host='127.0.0.1',
    port=9999
)


def explain_runtime(cur, sql):
    """返回单次 Total runtime（ms）"""
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, TIMING) {sql}")
    plan = '\n'.join(row[0] for row in cur.fetchall())
    m = TOTAL_RUNTIME_RE.search(plan)
    if not m:
        raise RuntimeError('Total runtime not found')
    return float(m.group(1))


def bench_file(cur, fpath, runs):
    sql = fpath.read_text().strip()
    times = [explain_runtime(cur, sql) for _ in range(runs)]
    return times


def main():
    parser = argparse.ArgumentParser(description='openGauss EXPLAIN ANALYZE benchmark')
    parser.add_argument('-n', '--runs', type=int, default=5, help='每条语句跑几次')
    parser.add_argument('files', nargs='+', help='要测试的 .sql 文件')
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONF)
    conn.autocommit = True
    cur = conn.cursor()

    csv_rows = []
    for f in args.files:
        p = Path(f)
        times = bench_file(cur, p, args.runs)
        median = statistics.median(times)
        csv_rows.append([p.name, median] + times)
        print(f"{p.name}: median {median:.3f} ms  (runs: {' '.join(f'{t:.3f}' for t in times)})")

    # 写结果
    with open('result.csv', 'w', newline='') as cf:
        w = csv.writer(cf)
        w.writerow(['file', 'median_ms'] + [f'run{i+1}_ms' for i in range(args.runs)])
        w.writerows(csv_rows)

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()

# python3 ./bench_og.py q4.sql q5.sql q6.sql q7.sql q8.sql q12.sql q14.sql q15.sql