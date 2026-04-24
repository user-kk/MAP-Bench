#!/usr/bin/env python
"""
AgensGraph 性能基准脚本（支持指定并行度 + 实时落盘）
用法:
    python bench_agensgraph.py *.sql -n 10 -t 8 -o result.csv -d mapm
"""
import argparse
import csv
import statistics
import sys
import time
from pathlib import Path
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from benchmark_config import (
    get_dataset_conf,
    get_query_params,
    load_benchmark_config,
    render_query_template,
)

DB_CONF = dict(
    dbname='mapl',
    user='agensgraph',
    password='linux123',
    host='127.0.0.1',
    port=5555,
)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / 'common' / 'benchmark_config.json'


def setup_session(cur, max_parallel: int):
    cur.execute('SET graph_path = academic_net')
    cur.execute('SET plan_cache_mode = force_custom_plan')
    cur.execute(f'SET max_parallel_workers_per_gather = {max_parallel}')
    if max_parallel == 0:
        cur.execute("SET work_mem = '12GB'")
    else:
        cur.execute("SET work_mem = '2GB'")


def explain_runtime(cur, sql: str) -> float:
    t0 = time.perf_counter()
    cur.execute(sql)
    cur.fetchall()
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
    parser = argparse.ArgumentParser(description='AgensGraph SQL Benchmark Tool')
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='每条 SQL 跑几轮（默认 5）')
    parser.add_argument('-t', '--threads', type=int, default=0,
                        help='设置 max_parallel_workers_per_gather (默认 0)')
    parser.add_argument('-d', '--dataset', choices=['mapl', 'mapm', 'maps'], default='mapl',
                        help='选择数据集（默认 mapl）')
    parser.add_argument('-c', '--config', type=Path, default=DEFAULT_CONFIG_PATH,
                        help='配置文件路径（默认 script/common/benchmark_config.json）')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 路径（默认 result.csv）')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .sql 文件')
    parser.add_argument('files', nargs='+', help='待测试 .sql 文件')
    args = parser.parse_args()

    config = load_benchmark_config(args.config)
    dataset_conf = get_dataset_conf(config, 'agensgraph', args.dataset)

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files
                        if Path(f).name not in exclude_set],
                       key=lambda p: p.name)

    if not file_list:
        print('没有找到可执行的 SQL 文件。')
        return

    data = {f.name: [] for f in file_list}
    db_conf = DB_CONF.copy()
    db_conf['dbname'] = dataset_conf['db_name']

    try:
        conn = psycopg.connect(**db_conf)
        conn.autocommit = True
        cur = conn.cursor()
        setup_session(cur, args.threads)
        flush_csv(args.out, data, args.rounds)

        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                sql = render_query_template(
                    f.read_text(encoding='utf-8').strip(),
                    get_query_params(config, 'agensgraph', f.stem, args.dataset),
                )
                if not sql:
                    continue
                try:
                    t = explain_runtime(cur, sql)
                    data[f.name].append(t)
                    print(f'Round {rnd}/{args.rounds} | {f.name}: {t:.3f} ms')
                except Exception as e:
                    print(f'  [Error] 执行 {f.name} 失败: {e}')
                    data[f.name].append(0.0)
                flush_csv(args.out, data, args.rounds)
    except Exception as e:
        print(f'\n[FATAL ERROR] {e}')
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
        print(f'\n测试完成，最终结果已保存至: {args.out}')


if __name__ == '__main__':
    main()
