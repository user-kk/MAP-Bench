#!/usr/bin/env python3
"""
HelmDB 执行计划获取器：先按轮次完成所有查询的预热，再统一使用 EXPLAIN ANALYZE 执行每个查询。
"""
import argparse
from pathlib import Path
import psycopg2
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from benchmark_config import (
    get_dataset_conf,
    get_query_params,
    load_benchmark_config,
    render_query_template,
)

DB_CONF = dict(
    dbname='mapl',
    user='hyh',
    password='Linux123',
    host='127.0.0.1',
    port=9999,
)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / 'common' / 'benchmark_config.json'


def main():
    parser = argparse.ArgumentParser(description='获取 HelmDB EXPLAIN ANALYZE 执行计划')
    parser.add_argument('-d', '--dataset', choices=['mapl', 'mapm', 'maps'], default='mapl',
                        help='选择数据集（默认 mapl）')
    parser.add_argument('-c', '--config', type=Path, default=DEFAULT_CONFIG_PATH,
                        help='配置文件路径（默认 script/common/benchmark_config.json）')
    parser.add_argument('-o', '--out', type=Path, default=Path('explain_plans.txt'),
                        help='输出文件路径 (默认: explain_plans.txt)')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='需要排除的 SQL 文件')
    parser.add_argument('--warmup', type=int, default=0,
                        help='预热轮数 (不计时，用于缓存预热，默认: 0)')
    parser.add_argument('files', nargs='+', help='待测 .sql 文件')
    args = parser.parse_args()

    config = load_benchmark_config(args.config)
    dataset_conf = get_dataset_conf(config, 'helmdb', args.dataset)

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files if Path(f).name not in exclude_set], key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    queries = []
    for f in file_list:
        sql = render_query_template(
            f.read_text(encoding='utf-8').strip(),
            get_query_params(config, 'helmdb', f.stem, args.dataset),
        )
        queries.append((f, sql))

    db_conf = DB_CONF.copy()
    db_conf['dbname'] = dataset_conf['db_name']
    conn = psycopg2.connect(**db_conf)
    cur = conn.cursor()
    cur.execute('SET enable_pbe_optimization = off')
    separator = '=' * 80

    if args.warmup > 0:
        print(f'开始预热，共 {args.warmup} 轮，每轮执行 {len(queries)} 个查询...')
        for warmup_round in range(1, args.warmup + 1):
            print(f'Warmup round {warmup_round}/{args.warmup}')
            for f, sql in queries:
                print(f'  Warmup: {f.name}')
                try:
                    cur.execute(sql)
                    if cur.description:
                        cur.fetchall()
                    print('    OK')
                except Exception as e:
                    error_msg = f'ERROR: {type(e).__name__}: {e}'
                    print(f'    {error_msg}')
                    conn.rollback()
        print('预热完成。\n')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf-8') as out_f:
        out_f.write('HelmDB EXPLAIN ANALYZE Results\n')
        out_f.write(f'Dataset: {args.dataset}\n')
        out_f.write(f'Warmup rounds: {args.warmup}\n')
        out_f.write(f'{separator}\n\n')

        print(f'开始获取执行计划，共 {len(queries)} 个查询...')
        for f, sql in queries:
            print(f'Processing EXPLAIN ANALYZE: {f.name}')
            out_f.write(f'{separator}\n')
            out_f.write(f'File: {f.name}\n')
            out_f.write(f'{separator}\n\n')
            out_f.write('-- Original SQL:\n')
            out_f.write(sql)
            out_f.write('\n\n')
            explain_sql = 'EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) ' + sql
            try:
                cur.execute(explain_sql)
                rows = cur.fetchall()
                out_f.write('QUERY PLAN:\n')
                for row in rows:
                    out_f.write(row[0] + '\n')
                out_f.write('\n')
                print('  EXPLAIN ANALYZE: OK')
            except Exception as e:
                error_msg = f'ERROR: {type(e).__name__}: {e}'
                out_f.write(error_msg + '\n\n')
                print(f'  EXPLAIN ANALYZE: {error_msg}')
                conn.rollback()
            out_f.write('\n')

    print(f'\n执行计划已写入: {args.out}')
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
