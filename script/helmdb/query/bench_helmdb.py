#!/usr/bin/env python
"""
openGauss MMSQL 性能基准脚本（每单次立即落盘 + 实时中位数 + 中位数第二列）

用法:
    python3 bench_helmdb.py *.sql -n 10 -o result.csv -x a.sql b.sql c.sql

CSV 格式:
    file,median_ms,run1_ms,run2_ms,...,runN_ms

依赖:
    pip install psycopg2-binary
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
    """返回端到端耗时（毫秒）"""
    t0 = time.perf_counter()
    cur.execute(sql)
    cur.fetchall()
    t1 = time.perf_counter()
    return (t1 - t0) * 1000

def flush_csv(out: Path, data: dict, runs: int):
    """实时重写整个 CSV 文件（中位数放第二列）"""
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
    # 关键：-x 后面可跟任意数量文件名
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .sql 文件（可一次写多个，空格隔开）')
    parser.add_argument('files', nargs='+', help='待测试 .sql 文件')
    args = parser.parse_args()

    # 把排除名单做成绝对路径集合，方便快速判断
    exclude_set = {Path(f).resolve() for f in args.exclude}

    # 过滤掉被排除的文件
    file_list = sorted(
        [Path(f) for f in args.files if Path(f).resolve() not in exclude_set],
        key=lambda p: p.name
    )
    
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    data = {f.name: [] for f in file_list}

    conn = psycopg2.connect(**DB_CONF)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET enable_pbe_optimization = off")
    cur.execute("ALTER SYSTEM SET enable_global_plancache = off")

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