#!/usr/bin/env python3
"""
openGauss MMSQL 性能基准脚本（每单次立即落盘 + 实时中位数 + 中位数第二列）
用法:  python3 bench_helmdb.py q4.sql q5.sql …  [-n 10] [-o result.csv]
CSV 格式: file,median_ms,run1_ms,run2_ms,…,runN_ms
依赖:  pip install psycopg2-binary
"""
import argparse
import csv
import re
import statistics
import psycopg2
from pathlib import Path

TOTAL_RUNTIME_RE = re.compile(r'Total\s+runtime:\s+(\d+(?:\.\d+)?)\s*ms', re.I)

DB_CONF = dict(
    dbname='openalex_middle',
    user='hyh',
    password='Linux123',
    host='127.0.0.1',
    port=9999
)

# ---------- 工具 ----------
def explain_runtime(cur, sql: str) -> float:
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, TIMING) {sql}")
    plan = '\n'.join(row[0] for row in cur.fetchall())
    m = TOTAL_RUNTIME_RE.search(plan)
    if not m:
        raise RuntimeError('Total runtime not found')
    return float(m.group(1))

def flush_csv(out: Path, data: dict, runs: int):
    """实时重写整个文件（中位数第二列）"""
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

# ---------- 主流程 ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5)
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('files', nargs='+', help='待测试 .sql 文件')
    args = parser.parse_args()

    file_list = [Path(f) for f in args.files]
    data = {f.name: [] for f in file_list}

    conn = psycopg2.connect(**DB_CONF)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET enable_pbe_optimization = off")
    cur.execute("ALTER SYSTEM SET enable_global_plancache = off")

    try:
        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                sql = f.read_text().strip()
                t = explain_runtime(cur, sql)
                data[f.name].append(t)
                print(f'R{rnd:02d}  {f.name}: {t:.3f} ms')
                flush_csv(args.out, data, args.rounds)
    except Exception as e:
        print(f'\n[ERROR] {e}  ——  已跑结果已实时写入')
        raise
    finally:
        print(f'结果实时写入 {args.out}')
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()