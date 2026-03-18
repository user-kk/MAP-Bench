#!/usr/bin/env python3
"""
Polystore 性能基准脚本
用法:
    python3 bench_polystore.py *.py -n 10 -o result.csv -x exclude1.py exclude2.py

CSV 格式:
    file,median_ms,run1_ms,run2_ms,...,runN_ms
"""
import argparse
import csv
import statistics
import time
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List
import warnings
warnings.simplefilter("ignore", UserWarning)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.context import get_context,Context

DB_CONF = dict(
    host='127.0.0.1',
    pg_port=30000,
    mongo_port=30001,
    neo4j_port=30003,
    milvus_port=30004,
    user="root",
    pwd="linux123",
    db_name='mapl'
)

# ---------- 工具 ----------
def run_single(py_file: Path, ctx: Context) -> float:
    """
    动态导入 py_file，执行同名函数 Xxx(ctx: Context)，返回端到端耗时（毫秒）
    """
    mod_name = py_file.stem
    spec = importlib.util.spec_from_file_location(mod_name, py_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {py_file}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    func = getattr(mod, mod_name, None)
    if func is None or not callable(func):
        raise RuntimeError(f"{py_file} 中找不到名为 {mod_name} 的可调用对象")

    t0 = time.perf_counter()
    func(ctx)          # 把 Context 实例传进去
    t1 = time.perf_counter()
    return (t1 - t0) * 1000


def flush_csv(out: Path, data: Dict[str, List[float]], runs: int):
    """实时重写整个文件（中位数第二列）"""
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

# ---------- 主流程 ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='每个 .py 跑几轮（默认 5）')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 路径（默认 result.csv）')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .py 文件（可一次写多个，空格隔开）')
    parser.add_argument('files', nargs='+', help='待测试 .py 文件')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}          
    file_list = sorted([Path(f).resolve() for f in args.files
                    if Path(f).name not in exclude_set],    
                   key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    data = {f.name: [] for f in file_list}

    # 全局唯一 Context，所有测试复用同一个连接
    ctx = get_context(host=DB_CONF['host'],
                      pg_port=DB_CONF['pg_port'],
                      mongo_port=DB_CONF['mongo_port'],
                      neo4j_port=DB_CONF['neo4j_port'],
                      milvus_port=DB_CONF['milvus_port'],
                      user=DB_CONF['user'],
                      pwd=DB_CONF['pwd'])
    
    ctx.use(DB_CONF['db_name'])

    try:
        flush_csv(args.out, data, args.rounds)
        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                t = run_single(f, ctx)   # 把 ctx 传进去
                data[f.name].append(t)
                print(f'R{rnd:02d}  {f.name}: {t:.3f} ms')
                flush_csv(args.out, data, args.rounds)
    except Exception as e:
        print(f'\n[ERROR] {e}  ——  已跑结果已实时写入')
        raise
    finally:
        print(f'结果实时写入 {args.out}')
        ctx.close()

if __name__ == '__main__':
    main()