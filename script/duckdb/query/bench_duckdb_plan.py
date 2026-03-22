#!/usr/bin/env python3
import argparse
from pathlib import Path
import duckdb
import json
import sys

DB_CONF = dict(
    db_path='/duckdb_data/mapl.db'
)

SEPARATOR = "=" * 80


def run_explain_analyze(conn: duckdb.DuckDBPyConnection, sql: str) -> str:
    explain_sql = "EXPLAIN (ANALYZE, FORMAT JSON)\n" + sql
    raw = conn.execute(explain_sql).fetchone()[1]
    obj = json.loads(raw)
    plan = obj[0] if isinstance(obj, list) else obj
    return json.dumps(plan, separators=(',', ':'), ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description='获取 DuckDB EXPLAIN ANALYZE 执行计划 (JSON 格式)')
    parser.add_argument('-o', '--out', type=Path, default=Path('duckdb_plans.txt'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('--warmup', type=int, default=0)
    parser.add_argument('-t', '--threads', type=int, default=None)
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted(
        [Path(f).resolve() for f in args.files if Path(f).name not in exclude_set],
        key=lambda p: p.name
    )
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    queries = [(f, f.read_text(encoding='utf-8').strip()) for f in file_list]

    conn = duckdb.connect(DB_CONF['db_path'], config={'allow_unsigned_extensions': 'true'})
    try:
        conn.execute("INSTALL duckpgq FROM community; INSTALL vss;")
        conn.execute("LOAD duckpgq; LOAD vss;")
        conn.execute("PRAGMA enable_profiling;")

        if args.threads is not None:
            conn.execute(f"SET threads={args.threads}")

        if args.warmup > 0:
            print(f'开始预热，共 {args.warmup} 轮，每轮执行 {len(queries)} 个查询...')
            for warmup_round in range(1, args.warmup + 1):
                print(f'Warmup round {warmup_round}/{args.warmup}')
                for f, sql in queries:
                    print(f'  Warmup: {f.name}')
                    try:
                        conn.execute(sql).fetchall()
                        print('    OK')
                    except KeyboardInterrupt:
                        print('\n检测到 Ctrl+C，立即退出。')
                        raise
                    except Exception as e:
                        print(f'    ERROR: {type(e).__name__}: {e}')
            print('预热完成。\n')

        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('w', encoding='utf-8') as out_f:
            out_f.write("DuckDB EXPLAIN ANALYZE Results (JSON format)\n")
            out_f.write(f"Threads: {args.threads if args.threads is not None else 'auto'}\n")
            out_f.write(f"Warmup rounds: {args.warmup}\n")
            out_f.write(f"{SEPARATOR}\n\n")

            print(f'开始获取执行计划，共 {len(queries)} 个查询...')
            for f, sql in queries:
                print(f'Processing EXPLAIN ANALYZE: {f.name}')

                out_f.write(f"{SEPARATOR}\n")
                out_f.write(f"File: {f.name}\n")
                out_f.write(f"{SEPARATOR}\n\n")
                out_f.write("-- Original SQL:\n")
                out_f.write(sql)
                out_f.write("\n\n")

                try:
                    plan_output = run_explain_analyze(conn, sql)
                    out_f.write("QUERY PLAN (JSON):\n")
                    out_f.write(plan_output)
                    out_f.write("\n\n")
                    print('  EXPLAIN ANALYZE: OK')
                except KeyboardInterrupt:
                    print('\n检测到 Ctrl+C，立即退出。')
                    raise
                except Exception as e:
                    error_msg = f"ERROR: {type(e).__name__}: {e}"
                    out_f.write(error_msg + "\n\n")
                    print(f'  EXPLAIN ANALYZE: {error_msg}')

                out_f.write("\n")

        print(f'\n执行计划已写入: {args.out}')
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('用户中断。')
        sys.exit(130)