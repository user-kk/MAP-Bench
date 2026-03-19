#!/usr/bin/env python3
"""
DuckDB 执行计划获取器：使用 EXPLAIN ANALYZE 执行每个查询，
将完整执行计划输出到一个 txt 文件中。

用法:
    python3 bench_duckdb_plan.py sql/*.sql -x exclude.sql --warmup 3 -t 4 -o plans.txt
"""
import argparse
from pathlib import Path
import duckdb
import json

DB_CONF = dict(
    db_path='/duckdb_data/mapl.db'
)

SEPARATOR = "=" * 80


def run_explain_analyze(conn: duckdb.DuckDBPyConnection, sql: str) -> str:
    """执行 EXPLAIN ANALYZE (FORMAT JSON) 并返回格式化的 JSON 执行计划"""
    explain_sql = "EXPLAIN (ANALYZE, FORMAT JSON) \n" + sql
    raw = conn.execute(explain_sql).fetchone()[1]
    # 格式化 JSON 输出
    plan = json.loads(raw)[0] if isinstance(json.loads(raw), list) else json.loads(raw)
    return json.dumps(plan, separators=(',', ':'), ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description='获取 DuckDB EXPLAIN ANALYZE 执行计划 (JSON 格式)')
    parser.add_argument('-o', '--out', type=Path, default=Path('duckdb_plans.txt'),
                        help='输出文件路径 (默认: duckdb_plans.txt)')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='需要排除的 SQL 文件')
    parser.add_argument('--warmup', type=int, default=0,
                        help='预热轮数 (不计时，用于缓存预热，默认: 0)')
    parser.add_argument('-t', '--threads', type=int, default=None,
                        help='设置 threads (默认使用 DuckDB 自动配置)')
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

    conn = duckdb.connect(DB_CONF['db_path'], config={'allow_unsigned_extensions': 'true'})
    # 按需加载扩展
    conn.execute("INSTALL duckpgq FROM community; INSTALL vss;")
    conn.execute("LOAD duckpgq; LOAD vss;")
    conn.execute("PRAGMA enable_profiling;")

    # 设置线程数
    if args.threads is not None:
        conn.execute(f"SET threads={args.threads}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf-8') as out_f:
        out_f.write(f"DuckDB EXPLAIN ANALYZE Results (JSON format)\n")
        if args.threads is not None:
            out_f.write(f"Threads: {args.threads}\n")
        else:
            out_f.write(f"Threads: auto\n")
        out_f.write(f"Warmup rounds: {args.warmup}\n")
        out_f.write(f"{SEPARATOR}\n\n")

        for f in file_list:
            sql = f.read_text().strip()
            print(f'Processing: {f.name}')

            out_f.write(f"{SEPARATOR}\n")
            out_f.write(f"File: {f.name}\n")
            out_f.write(f"{SEPARATOR}\n\n")

            # 写入原始 SQL
            out_f.write("-- Original SQL:\n")
            out_f.write(sql)
            out_f.write("\n\n")

            # 预热阶段：执行但不获取执行计划
            if args.warmup > 0:
                print(f'  Warmup phase ({args.warmup} rounds)...')
                for warmup_idx in range(1, args.warmup + 1):
                    try:
                        conn.execute(sql).fetchall()
                        print(f'    Warmup {warmup_idx}/{args.warmup}: OK')
                    except Exception as e:
                        error_msg = f"ERROR: {type(e).__name__}: {e}"
                        print(f'    Warmup {warmup_idx}/{args.warmup}: {error_msg}')
                print(f'  Warmup completed.')

            # 正式执行：获取 EXPLAIN ANALYZE 结果
            try:
                plan_output = run_explain_analyze(conn, sql)
                out_f.write("QUERY PLAN (JSON):\n")
                out_f.write(plan_output)
                out_f.write("\n\n")
                print(f'  EXPLAIN ANALYZE: OK')
            except Exception as e:
                error_msg = f"ERROR: {type(e).__name__}: {e}"
                out_f.write(error_msg + "\n\n")
                print(f'  EXPLAIN ANALYZE: {error_msg}')

            out_f.write("\n")

    print(f'\n执行计划已写入: {args.out}')
    conn.close()


if __name__ == '__main__':
    main()