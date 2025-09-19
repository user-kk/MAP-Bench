#!/usr/bin/env python3
import argparse
import csv
import re
import statistics
import psycopg2
from pathlib import Path

"""
openGauss MMSQL 性能基准脚本
用法:  python3 bench_og.py  q4.sql q5.sql  [-n 5] [-o my.csv]
输出:  终端实时中位数 + 指定 csv
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

def explain_runtime(cur, sql: str) -> float:
    """返回单次 Total runtime（ms）"""
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
    """把已跑数据落盘"""
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as cf:
        w = csv.writer(cf)
        w.writerow(['file', 'median_ms'] + [f'run{i+1}_ms' for i in range(runs)])
        w.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description='openGauss EXPLAIN ANALYZE benchmark')
    parser.add_argument('-n', '--runs', type=int, default=5, help='每条语句跑几次')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 文件路径 (默认: result.csv)')
    parser.add_argument('files', nargs='+', help='要测试的 .sql 文件')
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONF)
    conn.autocommit = True
    cur = conn.cursor()

     # ---------- 禁用各类缓存 ----------
    cur.execute("SET enable_pbe_optimization = off")      # 会话级计划缓存
    cur.execute("ALTER SYSTEM SET enable_global_plancache = off")      # 全局计划缓存（会话视角立即生效）

    csv_rows = []
    try:
        for f in map(Path, args.files):
            times = bench_file(cur, f, args.runs)
            median = statistics.median(times)
            csv_rows.append([f.name, median] + times)
            print(f"{f.name}: median {median:.3f} ms")
    except Exception as e:
        print(f'\n[ERROR] {e}  ——  已跑结果先落盘')
        raise                                    # 如需继续抛出
    finally:
        if csv_rows:                             # 有任何成功结果就写
            write_csv(args.out, csv_rows, args.runs)
            print(f'结果已写入 {args.out}')
        else:
            print('无任何成功结果，CSV 未生成')
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()