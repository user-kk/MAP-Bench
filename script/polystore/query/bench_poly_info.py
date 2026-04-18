#!/usr/bin/env python3
"""
Polystore 复杂度分析脚本 (函数级精准计数版)
"""
import argparse
import csv
import importlib.util
import sys
import time
import tokenize
import ast
from pathlib import Path
import warnings

warnings.simplefilter('ignore', UserWarning)


def load_source(module_name, file_path):
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f'Cannot find module file: {file_path}')
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load module from {file_path}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


script_common = Path(__file__).resolve().parents[2] / 'common'
path_to_sqt = script_common / 'split_query_tokens.py'
sqt_mod = load_source('sqt_utils', path_to_sqt)
split_query_tokens = sqt_mod.split_query_tokens
cfg_mod = load_source('bench_cfg_utils', script_common / 'benchmark_config.py')
load_benchmark_config = cfg_mod.load_benchmark_config
get_dataset_conf = cfg_mod.get_dataset_conf
get_query_params = cfg_mod.get_query_params
DEFAULT_CONFIG_PATH = script_common / 'benchmark_config.json'

base_path = Path(__file__).resolve().parent.parent / 'common'
ctx_mod = load_source('bench_context', base_path / 'context.py')
timer_mod = load_source('bench_timer', base_path / 'timer.py')
get_context = ctx_mod.get_context
Context = ctx_mod.Context
MDTimer = timer_mod.MultiDatabaseTimer

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


def is_likely_query(text: str) -> bool:
    text = text.strip().upper()
    keywords = ['SELECT', 'WITH', 'MATCH', 'CREATE', 'UNWIND', 'MERGE']
    for kw in keywords:
        if text.startswith(kw):
            return True
    return False


def get_function_span(file_path: Path, func_name: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return (node.lineno, node.end_lineno)
    except Exception as e:
        print(f'[AST Error] {file_path.name}: {e}')
    return None


def count_target_function_tokens(file_path: Path) -> int:
    func_name = file_path.stem
    span = get_function_span(file_path, func_name)
    if not span:
        print(f"[Warn] No function named '{func_name}' found in {file_path.name}")
        return 0
    start_line, end_line = span
    token_count = 0

    with file_path.open('rb') as f:
        try:
            tokens = tokenize.tokenize(f.readline)
            for token in tokens:
                if token.start[0] < start_line or token.start[0] > end_line:
                    continue
                if token.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                                  tokenize.ENCODING, tokenize.ENDMARKER,
                                  tokenize.INDENT, tokenize.DEDENT):
                    continue
                if token.type == tokenize.STRING:
                    try:
                        content = ast.literal_eval(token.string)
                        if isinstance(content, str) and is_likely_query(content):
                            sub_tokens = split_query_tokens(content)
                            token_count += len(sub_tokens)
                        else:
                            token_count += 1
                    except Exception:
                        token_count += 1
                else:
                    token_count += 1
        except tokenize.TokenError:
            return 0
    return token_count


def run_and_profile(py_file: Path, ctx: Context, params: dict) -> str:
    mod_name = py_file.stem
    spec = importlib.util.spec_from_file_location(mod_name, py_file)
    if spec is None:
        return 'LoadError'
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    func = getattr(mod, mod_name, None)
    if not func:
        return 'NoFunc'

    timer = MDTimer()
    t_start = time.perf_counter()
    try:
        call_params = dict(params)
        call_params['timer'] = timer
        func(ctx, **call_params)
    except Exception as e:
        print(f'Error in {mod_name}: {e}')
        return 'RunErr'
    t_end = time.perf_counter()

    total_wall_time = (t_end - t_start) * 1000
    times_map = timer.get_times_map()
    total_db_time = sum(times_map.values())
    glue_time = max(0, total_wall_time - total_db_time)
    times_map['py'] = glue_time

    if total_wall_time == 0:
        return '0ms'

    items = sorted(times_map.items(), key=lambda x: x[1], reverse=True)
    parts = []
    for m, t in items:
        if t > 0.1:
            parts.append(f'{m}:{t:.1f}ms({t/total_wall_time*100:.1f}%)')
    return ' '.join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dataset', choices=['mapl', 'mapm', 'maps'], default='mapl',
                        help='选择数据集（默认 mapl）')
    parser.add_argument('-c', '--config', type=Path, default=DEFAULT_CONFIG_PATH,
                        help='配置文件路径（默认 script/common/benchmark_config.json）')
    parser.add_argument('-o', '--out', type=Path, default=Path('poly_complexity.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+', help='Files')
    args = parser.parse_args()

    config = load_benchmark_config(args.config)
    dataset_conf = get_dataset_conf(config, 'polystore', args.dataset)

    exclude_set = {Path(f).name for f in args.exclude}
    files = sorted([Path(f).resolve() for f in args.files if Path(f).name not in exclude_set], key=lambda x: x.name)
    if not files:
        return

    ctx = get_context(
        host=DB_CONF['host'],
        pg_port=DB_CONF['pg_port'],
        mongo_port=DB_CONF['mongo_port'],
        neo4j_port=DB_CONF['neo4j_port'],
        milvus_port=DB_CONF['milvus_port'],
        user=DB_CONF['user'],
        pwd=DB_CONF['pwd'],
    )
    ctx.use(dataset_conf['db_name'])
    print(f'[INFO] Polystore 已切换 PG/MongoDB/Milvus 到 {dataset_conf["db_name"]}，请确认 Neo4j 已在外部切到同一数据集。')

    try:
        data = []
        print(f"{'File':<10} | {'Tokens':<6} | Breakdown")
        print('-' * 50)
        for f in files:
            tokens = count_target_function_tokens(f)
            breakdown = run_and_profile(f, ctx, get_query_params(config, 'polystore', f.stem, args.dataset))
            print(f'{f.name:<10} | {tokens:<6} | {breakdown}')
            data.append([f.name, tokens, breakdown])

        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('w', newline='') as f:
            csv.writer(f).writerows([['file', 'tokens', 'breakdown']] + data)
        print(f'\nSaved to {args.out}')
    finally:
        ctx.close()


if __name__ == '__main__':
    main()
