#!/usr/bin/env python
"""
AgensGraph 性能基准脚本（每单次立即落盘 + 实时中位数）
用法:
    python3 bench_agensgraph.py *.sql -n 10 -o result.csv -x exclude1.sql exclude2.sql

CSV 格式:
    file,median_ms,run1_ms,run2_ms,...,runN_ms

依赖:
    pip install "psycopg[binary]"
"""
import argparse
import csv
import re
import statistics
import psycopg
from pathlib import Path

TOTAL_RUNTIME_RE = re.compile(r'Execution\s+Time:\s+(\d+(?:\.\d+)?)\s*ms', re.I)

DB_CONF = dict(
    dbname='openalex_middle',
    user='agensgraph',
    password='linux123',
    host='127.0.0.1',
    port=5555
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
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='每条 SQL 跑几轮（默认 5）')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 路径（默认 result.csv）')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .sql 文件（可一次写多个，空格隔开）')
    parser.add_argument('files', nargs='+', help='待测试 .sql 文件')
    args = parser.parse_args()

    # 把排除名单做成绝对路径集合，方便快速判断
    exclude_set = {Path(f).resolve() for f in args.exclude}

    # 过滤掉被排除的文件
    file_list = [Path(f) for f in args.files if Path(f).resolve() not in exclude_set]
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    data = {f.name: [] for f in file_list}

    conn = psycopg.connect(**DB_CONF)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET graph_path = academic_net")
    cur.execute("SET max_parallel_workers_per_gather = 0")
    cur.execute("SET plan_cache_mode = force_custom_plan")

    try:
        flush_csv(args.out, data, args.rounds)
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