#!/usr/bin/env python
"""
DuckDB 性能基准脚本（支持指定并行度 + 实时落盘）
用法:
    python3 bench_duckdb.py *.sql -n 5 -t 8 -o result.csv
"""
import argparse
import csv
import statistics
import duckdb
import time
from pathlib import Path

# 数据库路径配置
DB_CONF = dict(
    db_path = '/duckdb_data/openalex_middle.db' 
)

def setup_session(conn: duckdb.DuckDBPyConnection, threads: int):
    """统一的会话设置"""
    # 加载必要扩展
    conn.execute("INSTALL duckpgq FROM community;")
    conn.execute("INSTALL vss;")
    conn.execute("LOAD duckpgq;")
    conn.execute("LOAD vss;")

    # 设置并行度与内存限制
    print(f"[*] 配置会话: threads={threads}")
    conn.execute(f"SET threads={threads}")
    
    # 根据并行度动态调整内存（可选，此处保持默认或大内存）
    conn.execute("SET memory_limit='50GB'")

def explain_runtime(conn: duckdb.DuckDBPyConnection, sql: str) -> float:
    """返回执行耗时（毫秒）"""
    t0 = time.perf_counter()
    # 使用 fetchone() 确保触发执行并拉回至少一行结果
    conn.execute(sql).fetchone()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return elapsed_ms

def flush_csv(out: Path, data: dict, runs: int):
    """实时重写 CSV 文件，保持中位数在第二列"""
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
    parser = argparse.ArgumentParser(description='DuckDB SQL Benchmark Tool')
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='每条 SQL 跑几轮（默认 5）')
    parser.add_argument('-t', '--threads', type=int, default=1,
                        help='设置 DuckDB 并行线程数 (默认 1)')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 路径（默认 result.csv）')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .sql 文件')
    parser.add_argument('files', nargs='+', help='待测试 .sql 文件')
    args = parser.parse_args()

    # 排除逻辑
    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files
                        if Path(f).name not in exclude_set],
                       key=lambda p: p.name)
    
    if not file_list:
        print('无可用文件执行。')
        return

    data = {f.name: [] for f in file_list}

    try:
        # 初始化连接
        conn = duckdb.connect(DB_CONF["db_path"], config={"allow_unsigned_extensions": "true"})
        
        # 应用设置
        setup_session(conn, args.threads)

        flush_csv(args.out, data, args.rounds)
        
        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                sql = f.read_text().strip()
                if not sql: continue
                
                try:
                    t = explain_runtime(conn, sql)
                    data[f.name].append(t)
                    print(f'R{rnd:02d} {f.name}: {t:.3f} ms')
                except Exception as e:
                    print(f' [ERROR] {f.name}: {e}')
                    data[f.name].append(0.0)
                
                # 每次执行后实时落盘
                flush_csv(args.out, data, args.rounds)

    except Exception as e:
        print(f'\n[FATAL ERROR] {e}')
        raise
    finally:
        if 'conn' in locals():
            conn.close()
        print(f'\n测试结果已保存至: {args.out}')

if __name__ == '__main__':
    main()