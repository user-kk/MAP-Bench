#!/usr/bin/env python3
"""
AgensGraph EXPLAIN ANALYZE 性能基准脚本  
用法:  python3 bench_agensgraph.py  q4.sql q5.sql  [-n 5] [-o my.csv]  
输出:  终端实时中位数 + 指定 csv  
依赖:  pip install psycopg2-binary
"""

import argparse
import csv
import re
import statistics
import psycopg2
from pathlib import Path

TOTAL_RUNTIME_RE = re.compile(r'Execution\s+Time:\s+(\d+(?:\.\d+)?)\s*ms', re.I)
DB_CONF = dict(
    dbname='openalex_middle',  
    user='agensgraph',
    password='linux123',
    host='127.0.0.1',
    port=5555
)

def explain_runtime(cur, sql: str) -> float:
    """返回单次 Total runtime(ms)"""
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, TIMING) {sql}")
    plan = '\n'.join(row[0] for row in cur.fetchall())
    m = TOTAL_RUNTIME_RE.search(plan)
    if not m:
        raise RuntimeError('Total runtime not found')
    return float(m.group(1))

def bench_file(cur, fpath: Path, runs: int):
    sql = fpath.read_text().strip()
    return [explain_runtime(cur, sql) for _ in range(runs)]

def write_csv(out: Path, rows, runs: int):
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as cf:
        w = csv.writer(cf)
        w.writerow(['file', 'median_ms'] + [f'run{i+1}_ms' for i in range(runs)])
        w.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description='AgensGraph EXPLAIN ANALYZE benchmark')
    parser.add_argument('-n', '--runs', type=int, default=5, help='每条语句跑几次')
    parser.add_argument('-o', '--out', type=Path, default=Path('result_ag.csv'),
                        help='输出 csv 文件路径 (默认: result_ag.csv)')
    parser.add_argument('files', nargs='+', help='要测试的 .sql 文件')
    args = parser.parse_args()

    # 提前建好文件并写表头
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='') as cf:
        csv.writer(cf).writerow(
            ['file', 'median_ms'] + [f'run{i+1}_ms' for i in range(args.runs)]
        )

    conn = psycopg2.connect(**DB_CONF)
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute("SET graph_path = academic_net;")
    cur.execute("SET max_parallel_workers_per_gather = 0;")

    try:
        for f in map(Path, args.files):
            times = bench_file(cur, f, args.runs)
            median = statistics.median(times)
            # ****** 每跑完一条立即 append ******
            with args.out.open('a', newline='') as cf:
                csv.writer(cf).writerow([f.name, median] + times)
            print(f"{f.name}: median {median:.3f} ms")
    except Exception as e:
        print(f'\n[ERROR] {e}  ——  已跑结果已实时写入')
        raise
    finally:
        print(f'结果实时写入 {args.out}')
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()