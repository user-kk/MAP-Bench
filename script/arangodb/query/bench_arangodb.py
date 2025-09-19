#!/usr/bin/env python3
import statistics, csv, argparse
from pathlib import Path
from arango import ArangoClient, ArangoError         


"""
ArangoDB AQL 性能基准脚本
用法:  python3 bench_arangodb.py q4.aql q5.aql ...  [-n 5] [-o result.csv]
输出:  终端实时中位数 + 指定 csv
依赖:  pip install python-arango
"""

client = ArangoClient(hosts='http://127.0.0.1:8529')
db = client.db('openalex_middle', username='root', password='linux123')

def run_one(aql: str):
    cursor = db.aql.execute(aql, bind_vars={},
                            memory_limit=500 * 1024**3, profile=True)
    return cursor.statistics()['execution_time'] * 1000

def bench_file(fpath: Path, runs: int):
    aql = fpath.read_text().strip()
    return [run_one(aql) for _ in range(runs)]

def write_csv(out: Path, rows, runs: int):
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as cf:
        w = csv.writer(cf)
        w.writerow(['file', 'median_ms'] + [f'run{i+1}_ms' for i in range(runs)])
        w.writerows(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--runs', type=int, default=5)
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'))
    parser.add_argument('files', nargs='+', help='.aql files')
    args = parser.parse_args()

    rows = []
    try:
        for f in map(Path, args.files):
            times = bench_file(f, args.runs)
            median = statistics.median(times)
            rows.append([f.name, median] + times)
            print(f'{f.name}: median {median:.3f} ms')
    except Exception as e:                 # 任意异常（ArangoError、IO、…）
        print(f'\n[ERROR] {e}  ——  已跑结果先落盘')
    finally:                               # 无论成功/异常都写 CSV
        if rows:                           # 有数据才写
            write_csv(args.out, rows, args.runs)
            print(f'结果已写入 {args.out}')
        else:
            print('无任何成功结果，CSV 未生成')

if __name__ == '__main__':
    main()