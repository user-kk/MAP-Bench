#!/usr/bin/env python
"""
AgensGraph 性能基准脚本（支持指定并行度 + 实时落盘）
用法:
    python3 bench_agensgraph.py *.sql -n 10 -t 8 -o result.csv
"""
import argparse
import csv
import re
import statistics
import psycopg
import time
from pathlib import Path

# 数据库连接配置
DB_CONF = dict(
    dbname='mapl',
    user='agensgraph',
    password='linux123',
    host='127.0.0.1',
    port=5555
)

def setup_session(cur, max_parallel: int):
    """统一的会话设置"""
    cur.execute("SET graph_path = academic_net")
    cur.execute("SET plan_cache_mode = force_custom_plan")
    cur.execute(f"SET max_parallel_workers_per_gather = {max_parallel}")
    if max_parallel == 0:
        cur.execute("SET work_mem = '12GB'")
    else:
        # 并行度不为0时，减少每个 worker 的内存占用以防 OOM
        cur.execute("SET work_mem = '2GB'")

def explain_runtime(cur, sql: str) -> float:
    """返回端到端耗时（毫秒）"""
    t0 = time.perf_counter()
    cur.execute(sql)
    cur.fetchall()  # 确保结果完全传输
    t1 = time.perf_counter()
    return (t1 - t0) * 1000

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

def main():
    parser = argparse.ArgumentParser(description='AgensGraph SQL Benchmark Tool')
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='每条 SQL 跑几轮（默认 5）')
    parser.add_argument('-t', '--threads', type=int, default=0,
                        help='设置 max_parallel_workers_per_gather (默认 0)')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 路径（默认 result.csv）')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .sql 文件')
    parser.add_argument('files', nargs='+', help='待测试 .sql 文件')
    args = parser.parse_args()

    # 文件筛选
    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files
                        if Path(f).name not in exclude_set],
                       key=lambda p: p.name)
    
    if not file_list:
        print('没有找到可执行的 SQL 文件。')
        return

    data = {f.name: [] for f in file_list}

    try:
        conn = psycopg.connect(**DB_CONF)
        conn.autocommit = True
        cur = conn.cursor()

        # 应用并行度配置
        setup_session(cur, args.threads)

        flush_csv(args.out, data, args.rounds)
        
        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                sql = f.read_text().strip()
                if not sql:
                    continue
                
                try:
                    t = explain_runtime(cur, sql)
                    data[f.name].append(t)
                    print(f'Round {rnd}/{args.rounds} | {f.name}: {t:.3f} ms')
                except Exception as e:
                    print(f'  [Error] 执行 {f.name} 失败: {e}')
                    data[f.name].append(0.0) # 记录失败
                
                # 实时写入
                flush_csv(args.out, data, args.rounds)

    except Exception as e:
        print(f'\n[FATAL ERROR] {e}')
        raise
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()
        print(f'\n测试完成，最终结果已保存至: {args.out}')

if __name__ == '__main__':
    main()