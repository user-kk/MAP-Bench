#!/usr/bin/env python3
"""
AgensGraph 执行计划获取器：先按轮次完成所有查询的预热，
再统一使用 EXPLAIN ANALYZE 执行每个查询，
将完整执行计划输出到一个 txt 文件中。

用法:
    python3 bench_agensgraph_plan.py sql/*.sql -x exclude.sql --warmup 3 -o plans.txt
"""
import argparse
from pathlib import Path
import psycopg
from psycopg.types import TypeInfo
from psycopg.adapt import Loader

DB_CONF = dict(
    dbname='mapl',
    user='agensgraph',
    password='linux123',
    host='127.0.0.1',
    port=5555
)


class TextLoader(Loader):
    def load(self, data):
        return bytes(data).decode('utf-8')


def main():
    parser = argparse.ArgumentParser(
        description='获取 AgensGraph EXPLAIN ANALYZE 执行计划')
    parser.add_argument('-o', '--out', type=Path, default=Path('explain_plans.txt'),
                        help='输出文件路径 (默认: explain_plans.txt)')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='需要排除的 SQL 文件')
    parser.add_argument('--warmup', type=int, default=0,
                        help='预热轮数 (不计时，用于缓存预热，默认: 0)')
    parser.add_argument('-t', '--threads', type=int, default=0,
                        help='设置 max_parallel_workers_per_gather (默认 0)')
    parser.add_argument('files', nargs='+', help='待测 .sql 文件')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted(
        [Path(f).resolve() for f in args.files
         if Path(f).name not in exclude_set],
        key=lambda p: p.name
    )
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    queries = []
    for f in file_list:
        sql = f.read_text(encoding='utf-8').strip()
        queries.append((f, sql))

    conn = psycopg.connect(**DB_CONF, autocommit=True)
    info = TypeInfo.fetch(conn, 'json')
    conn.adapters.register_loader(info.oid, TextLoader)

    cur = conn.cursor()
    cur.execute("SET graph_path = academic_net")
    cur.execute("SET plan_cache_mode = force_custom_plan")
    cur.execute(f"SET max_parallel_workers_per_gather = {args.threads}")

    separator = "=" * 80

    # 第一阶段：先整轮预热，但不写入输出文件
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
                    error_msg = f"ERROR: {type(e).__name__}: {e}"
                    print(f'    {error_msg}')
                    conn.rollback() if not conn.autocommit else None
        print('预热完成。\n')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf-8') as out_f:
        out_f.write("AgensGraph EXPLAIN ANALYZE Results\n")
        out_f.write(f"Parallel workers: {args.threads}\n")
        out_f.write(f"Warmup rounds: {args.warmup}\n")
        out_f.write(f"{separator}\n\n")

        # 第二阶段：统一执行 EXPLAIN ANALYZE
        print(f'开始获取执行计划，共 {len(queries)} 个查询...')
        for f, sql in queries:
            print(f'Processing EXPLAIN ANALYZE: {f.name}')

            out_f.write(f"{separator}\n")
            out_f.write(f"File: {f.name}\n")
            out_f.write(f"{separator}\n\n")

            out_f.write("-- Original SQL:\n")
            out_f.write(sql)
            out_f.write("\n\n")

            explain_sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + sql

            try:
                cur.execute(explain_sql)
                rows = cur.fetchall()

                out_f.write("QUERY PLAN:\n")
                for row in rows:
                    out_f.write(row[0] + "\n")
                out_f.write("\n")

                print('  EXPLAIN ANALYZE: OK')

            except Exception as e:
                error_msg = f"ERROR: {type(e).__name__}: {e}"
                out_f.write(error_msg + "\n\n")
                print(f'  EXPLAIN ANALYZE: {error_msg}')
                conn.rollback() if not conn.autocommit else None

            out_f.write("\n")

    print(f'\n执行计划已写入: {args.out}')
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()