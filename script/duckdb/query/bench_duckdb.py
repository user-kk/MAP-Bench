#!/usr/bin/env python
import argparse
import csv
import statistics
import duckdb
import time
import sys
from pathlib import Path

DB_CONF = dict(
    db_path = '/duckdb_data/openalex_middle.db' 
)

def setup_session(conn, threads: int):
    conn.execute("INSTALL duckpgq FROM community;")
    conn.execute("INSTALL vss;")
    conn.execute("LOAD duckpgq;")
    conn.execute("LOAD vss;")
    print(f"[*] 配置会话: threads={threads}")
    conn.execute(f"SET threads={threads}")

def explain_runtime(conn, sql: str) -> float:
    t0 = time.perf_counter()
    conn.execute(sql).fetchone()
    return (time.perf_counter() - t0) * 1000

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
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5)
    parser.add_argument('-t', '--threads', type=int, default=1)
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files if Path(f).name not in exclude_set], key=lambda p: p.name)
    
    if not file_list:
        print('无文件可跑')
        return

    data = {f.name: [] for f in file_list}
    conn = duckdb.connect(DB_CONF["db_path"], config={"allow_unsigned_extensions": "true"})

    try:
        setup_session(conn, args.threads)
        flush_csv(args.out, data, args.rounds)
        
        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                sql = f.read_text().strip()
                if not sql: continue
                
                # 执行并记录
                t = explain_runtime(conn, sql)
                data[f.name].append(t)
                print(f'R{rnd:02d} {f.name}: {t:.3f} ms')
                
                # 实时落盘
                flush_csv(args.out, data, args.rounds)

    except KeyboardInterrupt:
        print('\n[!] 检测到 Ctrl+C，正在停止并保存当前进度...')
    except Exception as e:
        print(f'\n[ERROR] {e}')
    finally:
        # 确保哪怕强制退出，文件也是最新的
        flush_csv(args.out, data, args.rounds)
        conn.close()
        print(f'结果已落盘至 {args.out}。退出程序。')
        sys.exit(0)

if __name__ == '__main__':
    main()