#!/usr/bin/env python3
"""
ArangoDB AQL 性能基准脚本（每单次结果立即落盘 + 实时中位数）
用法:  python3 bench_arangodb.py q4.aql q5.aql …  [-n 10] [-o result.csv] [-x exclude1.aql exclude2.aql]
CSV 格式: file,median_ms,run1_ms,run2_ms,…,runN_ms
依赖:  pip install python-arango
"""
import argparse
import csv
import statistics
from pathlib import Path
from arango import ArangoClient
from arango.http import DefaultHTTPClient


class MyHTTP(DefaultHTTPClient):
    REQUEST_TIMEOUT = 3600 * 6
    request_timeout = 3600 * 6


client = ArangoClient(hosts='http://127.0.0.1:8529', http_client=MyHTTP())
db = client.db('openalex_middle', username='root', password='linux123')

# ---------- 工具 ----------
def run_one(aql: str) -> float:
    """跑一次查询，返回 execution_time(ms)"""
    cursor = db.aql.execute(
        aql, bind_vars={}, memory_limit=500 * 1024 ** 3,
        profile=True, cache=False
    )
    return cursor.statistics()['execution_time'] * 1000


def flush_csv(out: Path, data: dict, runs: int):
    """
    data: {file: [r1, r2, …, 已跑次数]}
    立即重写整个文件（中位数放第二列）
    """
    header = ['file', 'median_ms'] + [f'run{i}_ms' for i in range(1, runs + 1)]
    rows = []
    for fname, times in data.items():
        median = statistics.median(times) if times else ''
        rows.append([fname, f'{median:.3f}' if times else ''] +
                    [f'{t:.3f}' for t in times] +
                    [''] * (runs - len(times)))  # 未跑列留空
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='') as cf:
        csv.writer(cf).writerows([header] + rows)


# ---------- 主流程 ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='每条 AQL 跑几轮（默认 5）')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 路径（默认 result.csv）')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .aql 文件（可一次写多个，空格隔开）')
    parser.add_argument('files', nargs='+', help='待测试 .aql 文件')
    args = parser.parse_args()

    # 把排除名单做成绝对路径集合，方便快速判断
    exclude_set = {Path(f).resolve() for f in args.exclude}

    # 过滤掉被排除的文件
    file_list = [Path(f) for f in args.files if Path(f).resolve() not in exclude_set]
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    data = {f.name: [] for f in file_list}  # 收集结果

    try:
        flush_csv(args.out, data, args.rounds)
        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                aql = f.read_text().strip()
                t = run_one(aql)
                data[f.name].append(t)
                print(f'R{rnd:02d}  {f.name}: {t:.3f} ms')
                # 每单次跑完立即落盘
                flush_csv(args.out, data, args.rounds)
    except Exception as e:
        print(f'\n[ERROR] {e}  ——  已跑结果已实时写入')
        raise
    finally:
        print(f'结果实时写入 {args.out}')


if __name__ == '__main__':
    main()