#!/usr/bin/env python3
"""
HelmDB 执行计划获取器：使用 EXPLAIN ANALYZE 执行每个查询，
将完整执行计划输出到一个 txt 文件中。

用法:
    python3 bench_helmdb_plan.py sql/*.sql -x exclude.sql --warmup 3 -o plans.txt
"""
import argparse
from pathlib import Path
import psycopg2

DB_CONF = dict(
    dbname='mapl',
    user='hyh',
    password='Linux123',
    host='127.0.0.1',
    port=9999
)


def main():
    parser = argparse.ArgumentParser(
        description='获取 HelmDB EXPLAIN ANALYZE 执行计划')
    parser.add_argument('-o', '--out', type=Path, default=Path('explain_plans.txt'),
                        help='输出文件路径 (默认: explain_plans.txt)')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='需要排除的 SQL 文件')
    parser.add_argument('--warmup', type=int, default=0,
                        help='预热轮数 (不计时，用于缓存预热，默认: 0)')
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

    conn = psycopg2.connect(**DB_CONF)

    cur = conn.cursor()
    cur.execute("SET enable_pbe_optimization = off")

    separator = "=" * 80

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf-8') as out_f:
        out_f.write(f"HelmDB EXPLAIN ANALYZE Results\n")
        out_f.write(f"Warmup rounds: {args.warmup}\n")
        out_f.write(f"{separator}\n\n")

        for f in file_list:
            sql = f.read_text().strip()
            print(f'Processing: {f.name}')

            out_f.write(f"{separator}\n")
            out_f.write(f"File: {f.name}\n")
            out_f.write(f"{separator}\n\n")

            # 写入原始 SQL
            out_f.write("-- Original SQL:\n")
            out_f.write(sql)
            out_f.write("\n\n")

            # 预热阶段：执行但不获取执行计划
            if args.warmup > 0:
                print(f'  Warmup phase ({args.warmup} rounds)...')
                for warmup_idx in range(1, args.warmup + 1):
                    try:
                        cur.execute(sql)
                        cur.fetchall() if cur.description else None
                        print(f'    Warmup {warmup_idx}/{args.warmup}: OK')
                    except Exception as e:
                        error_msg = f"ERROR: {type(e).__name__}: {e}"
                        print(f'    Warmup {warmup_idx}/{args.warmup}: {error_msg}')
                        conn.rollback() if not conn.autocommit else None
                print(f'  Warmup completed.')

            # 正式执行：获取 EXPLAIN ANALYZE 结果
            explain_sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) " + sql

            try:
                cur.execute(explain_sql)
                rows = cur.fetchall()

                out_f.write("QUERY PLAN:\n")
                for row in rows:
                    out_f.write(row[0] + "\n")
                out_f.write("\n")

                print(f'  EXPLAIN ANALYZE: OK')

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