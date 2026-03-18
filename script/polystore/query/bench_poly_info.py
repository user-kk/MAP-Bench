#!/usr/bin/env python3
"""
Polystore 复杂度分析脚本 (V3 - 函数级精准计数版)
改进:
    1. 只计算与文件名同名的主函数 (如 A1.py -> def A1(...)) 的 Token。
    2. 剔除 import、main 入口、Argparse 等无关胶水代码。
    3. 依然保留对内部 SQL 字符串的深度展开计数。

用法:
    python3 polystore_complexity_v3.py *.py -x exclude.py -o result.csv
"""
import argparse
import csv
import importlib.util
import sys
import time
import tokenize
import ast
import re
from pathlib import Path
import warnings
import os

warnings.simplefilter("ignore", UserWarning)

# ==============================================================================
# 解决同名模块冲突的辅助函数
# ==============================================================================
def load_source(module_name, file_path):
    """
    直接从文件路径加载模块，绕过 sys.modules 缓存和 sys.path 搜索。
    这样即使两个文件夹都叫 'common'，只要文件路径不同，就可以分别加载。
    """
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot find module file: {file_path}")
    
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    
    mod = importlib.util.module_from_spec(spec)
    # 这一步非常关键：为了让模块内部的相对导入（如有）能工作，但这通常只对包内引用有效。
    # 对于纯工具文件，这样就够了。
    spec.loader.exec_module(mod)
    return mod

# ==============================================================================
# 1. 导入 split_query_tokens (来自 ../../common/split_query_tokens.py)
# ==============================================================================
path_to_sqt = Path(__file__).resolve().parent.parent.parent / 'common' / 'split_query_tokens.py'

# 加载模块，起个不冲突的名字
sqt_mod = load_source("sqt_utils", path_to_sqt)
split_query_tokens = sqt_mod.split_query_tokens  # 获取函数引用

# ==============================================================================
# 2. 导入 Context, MDTimer (来自 ../common/context.py 和 timer.py)
# ==============================================================================
base_path = Path(__file__).resolve().parent.parent / 'common'

ctx_mod = load_source("bench_context", base_path / 'context.py')
timer_mod = load_source("bench_timer", base_path / 'timer.py')

# 获取类引用
get_context = ctx_mod.get_context
Context = ctx_mod.Context
MDTimer = timer_mod.MultiDatabaseTimer

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


def is_likely_query(text: str) -> bool:
    text = text.strip().upper()
    # 增加一些 Cypher/SQL 常用词
    keywords = ["SELECT", "WITH", "MATCH", "CREATE", "UNWIND", "MERGE"]
    for kw in keywords:
        if text.startswith(kw): return True
    return False

# ---------------------------------------------------------
# 1. 核心：AST 定位 + Token 过滤
# ---------------------------------------------------------
def get_function_span(file_path: Path, func_name: str):
    """
    解析文件 AST，找到目标函数的 (start_line, end_line)。
    如果找不到，返回 None。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                # Python 3.8+ ast 节点带有 end_lineno
                return (node.lineno, node.end_lineno)
    except Exception as e:
        print(f"[AST Error] {file_path.name}: {e}")
    return None

def count_target_function_tokens(file_path: Path) -> int:
    """
    只计算目标函数范围内的 Token，并对 SQL 字符串进行膨胀。
    """
    func_name = file_path.stem  # A1.py -> A1
    span = get_function_span(file_path, func_name)
    
    # 如果找不到同名函数，报错
    if not span:
        print(f"[Warn] No function named '{func_name}' found in {file_path.name}")
        return 0
    
    start_line, end_line = span
    token_count = 0

    with file_path.open('rb') as f:
        try:
            tokens = tokenize.tokenize(f.readline)
            for token in tokens:
                # 1. 范围过滤：只处理函数体内的行
                # token.start 是 (row, col)
                if token.start[0] < start_line or token.start[0] > end_line:
                    continue

                # 2. 类型过滤：排除注释、换行、缩进等
                if token.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, 
                                  tokenize.ENCODING, tokenize.ENDMARKER, 
                                  tokenize.INDENT, tokenize.DEDENT):
                    continue
                
                # 3. 混合计数：检查字符串是否是 SQL
                if token.type == tokenize.STRING:
                    try:
                        content = ast.literal_eval(token.string)
                        if isinstance(content, str) and is_likely_query(content):
                            sub_tokens = split_query_tokens(content)
                            token_count += len(sub_tokens)
                        else:
                            token_count += 1
                    except:
                        token_count += 1
                else:
                    token_count += 1
                    
        except tokenize.TokenError:
            return 0
            
    return token_count

# ---------------------------------------------------------
# 2. 动态执行 (保持不变)
# ---------------------------------------------------------
def run_and_profile(py_file: Path, ctx: Context) -> str:
    """
    动态执行脚本，计算各部分耗时占比，包括隐藏的 Python 胶水代码时间。
    """
    mod_name = py_file.stem
    spec = importlib.util.spec_from_file_location(mod_name, py_file)
    if spec is None: return "LoadError"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)

    func = getattr(mod, mod_name, None)
    if not func: return "NoFunc"

    timer = MDTimer()
    
    # 1. 记录总的物理时间 (Wall Clock Time)
    t_start = time.perf_counter()
    try:
        func(ctx, timer=timer)
    except Exception as e:
        print(f"Error in {mod_name}: {e}")
        return "RunErr"
    t_end = time.perf_counter()
    
    total_wall_time = (t_end - t_start) * 1000  # 转换为毫秒

    # 2. 获取数据库耗时 (DB Time)
    times_map = timer.get_times_map() # {'r': 100, 'd': 200, ...}
    total_db_time = sum(times_map.values())

    # 3. 计算胶水代码耗时 (Glue Time)
    # 注意：如果 timer 统计有重叠或者精度误差，glue_time 可能会微小负数，这里修正为 0
    glue_time = max(0, total_wall_time - total_db_time)
    
    # 将胶水时间加入统计字典，代号 'py' (Python) 或 'glue'
    times_map['py'] = glue_time

    if total_wall_time == 0: return "0ms"

    # 4. 排序并格式化
    # 格式: d:200ms(40%) py:150ms(30%) r:100ms(20%) ...
    items = sorted(times_map.items(), key=lambda x: x[1], reverse=True)
    parts = []
    for m, t in items:
        if t > 0.1: # 忽略微小的噪音
            parts.append(f"{m}:{t:.1f}ms({t/total_wall_time*100:.1f}%)")
            
    return " ".join(parts)

# ---------------------------------------------------------
# . Main
# ---------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--out', type=Path, default=Path('poly_complexity.csv'))
    parser.add_argument('-x', '--exclude', nargs='*', default=[])
    parser.add_argument('files', nargs='+', help='Files')
    args = parser.parse_args()

    exclude_set = {Path(f).name for f in args.exclude}
    files = sorted([Path(f).resolve() for f in args.files if Path(f).name not in exclude_set], key=lambda x: x.name)

    if not files: return

    ctx = get_context(
        host=DB_CONF['host'],
        pg_port=DB_CONF['pg_port'],
        mongo_port=DB_CONF['mongo_port'],
        neo4j_port=DB_CONF['neo4j_port'],
        milvus_port=DB_CONF['milvus_port'],
        user=DB_CONF['user'],
        pwd=DB_CONF['pwd']
    )
    ctx.use(DB_CONF['db_name'])

    try:
        data = []
        print(f"{'File':<10} | {'Tokens':<6} | Breakdown")
        print("-" * 50)
        
        for f in files:
            # 这里的 tokens 仅包含 def A1(...): 内部的逻辑
            tokens = count_target_function_tokens(f)
            breakdown = run_and_profile(f, ctx)
            
            print(f"{f.name:<10} | {tokens:<6} | {breakdown}")
            data.append([f.name, tokens, breakdown])

        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('w', newline='') as f:
            csv.writer(f).writerows([['file', 'tokens', 'breakdown']] + data)
        print(f"\nSaved to {args.out}")
        
    finally:
        ctx.close()

if __name__ == '__main__':
    main()