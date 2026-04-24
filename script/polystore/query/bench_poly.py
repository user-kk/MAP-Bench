#!/usr/bin/env python3
"""
Polystore 性能基准脚本
用法:
    python bench_poly.py *.py -n 10 -o result.csv -x exclude1.py exclude2.py -d mapm

CSV 格式:
    file,median_ms,run1_ms,run2_ms,...,runN_ms
"""
import argparse
import csv
import importlib.util
import statistics
import sys
import time
import warnings
from pathlib import Path
from typing import Dict, List

warnings.simplefilter('ignore', UserWarning)

SCRIPT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPT_ROOT / 'common'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmark_config import get_dataset_conf, get_query_params, load_benchmark_config
from common.context import Context, get_context

DB_CONF = dict(
    host='127.0.0.1',
    pg_port=30000,
    mongo_port=30001,
    neo4j_port=30003,
    milvus_port=30004,
    user='root',
    pwd='linux123',
    db_name='mapl',
)
DEFAULT_CONFIG_PATH = SCRIPT_ROOT / 'common' / 'benchmark_config.json'


def run_single(py_file: Path, ctx: Context, params: Dict[str, object]) -> float:
    mod_name = py_file.stem
    spec = importlib.util.spec_from_file_location(mod_name, py_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'无法加载 {py_file}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    func = getattr(mod, mod_name, None)
    if func is None or not callable(func):
        raise RuntimeError(f'{py_file} 中找不到名为 {mod_name} 的可调用对象')

    t0 = time.perf_counter()
    func(ctx, **params)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000


def flush_csv(out: Path, data: Dict[str, List[float]], runs: int):
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
    parser.add_argument('-n', '--rounds', type=int, default=5,
                        help='每个 .py 跑几轮（默认 5）')
    parser.add_argument('-d', '--dataset', choices=['mapl', 'mapm', 'maps'], default='mapl',
                        help='选择数据集（默认 mapl）')
    parser.add_argument('-c', '--config', type=Path, default=DEFAULT_CONFIG_PATH,
                        help='配置文件路径（默认 script/common/benchmark_config.json）')
    parser.add_argument('-o', '--out', type=Path, default=Path('result.csv'),
                        help='输出 csv 路径（默认 result.csv）')
    parser.add_argument('-x', '--exclude', nargs='*', default=[],
                        help='要排除的 .py 文件（可一次写多个，空格隔开）')
    parser.add_argument('files', nargs='+', help='待测试 .py 文件')
    args = parser.parse_args()

    config = load_benchmark_config(args.config)
    dataset_conf = get_dataset_conf(config, 'polystore', args.dataset)

    exclude_set = {Path(f).name for f in args.exclude}
    file_list = sorted([Path(f).resolve() for f in args.files
                    if Path(f).name not in exclude_set],
                   key=lambda p: p.name)
    if not file_list:
        print('所有文件均被排除，无事可做。')
        return

    data = {f.name: [] for f in file_list}

    ctx = get_context(host=DB_CONF['host'],
                      pg_port=DB_CONF['pg_port'],
                      mongo_port=DB_CONF['mongo_port'],
                      neo4j_port=DB_CONF['neo4j_port'],
                      milvus_port=DB_CONF['milvus_port'],
                      user=DB_CONF['user'],
                      pwd=DB_CONF['pwd'])

    ctx.use(dataset_conf['db_name'])
    print(f'[INFO] Polystore 已切换 PG/MongoDB/Milvus 到 {dataset_conf["db_name"]}，请确认 Neo4j 已在外部切到同一数据集。')

    try:
        flush_csv(args.out, data, args.rounds)
        for rnd in range(1, args.rounds + 1):
            for f in file_list:
                params = get_query_params(config, 'polystore', f.stem, args.dataset)
                t = run_single(f, ctx, params)
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
