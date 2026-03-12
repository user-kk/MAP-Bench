#!/usr/bin/env python3
import re
import math
import csv
import argparse
import sys
import statistics
import ast
from pathlib import Path

# ==========================================
# 1. 基础关键字库 (SQL + Cypher + AQL + DuckDB)
# ==========================================
BASE_KEYWORDS = {
    # --- SQL Standard & Common Extensions ---
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'JOIN', 'INNER', 'OUTER',
    'LEFT', 'RIGHT', 'ON', 'AS', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT',
    'OFFSET', 'UNION', 'ALL', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'VALUES', 'SET', 'WITH',
    'RECURSIVE', 'CAST', 'NULL', 'IS', 'LIKE', 'BETWEEN', 'EXISTS', 'ANY', 'LATERAL',
    'CROSS', 'MATERIALIZED', 'PARTITION', 'OVER', 'ROW_NUMBER',

    # --- Graph Extensions (Agens / DuckPGQ) ---
    'MATCH', 'OPTIONAL', 'RETURN', 'MERGE', 'DETACH', 'UNWIND', 'CALL', 'YIELD',
    'SHORTEST', 'PATH', 'NODES', 'SHORTESTPATH',
    'GRAPH_TABLE', 'COLUMNS', 'VERTICES',

    # --- AQL (ArangoDB) ---
    'FOR', 'FILTER', 'LET', 'COLLECT', 'AGGREGATE', 'SORT', 'LIMIT', 'RETURN',
    'INBOUND', 'OUTBOUND', 'ANY', 'GRAPH', 'SHORTEST_PATH', 'TO',
    'INTO', 'KEEP', 'WITH', 'REMOVE', 'INSERT', 'UPDATE', 'REPLACE',

    # --- Functions (Postgres / DuckDB / AQL) ---
    'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COUNT_DISTINCT',
    'LENGTH', 'CONCAT', 'TO_STRING', 'TO_NUMBER', 'TO_JSONB', 'SUBSTRING', 'FLOOR',
    'COALESCE', 'JSONB_ARRAY_ELEMENTS', 'JSONB_PATH_QUERY_ARRAY', 'JSON_AGG', 'ARRAY_AGG',
    'JSONB_BUILD_OBJECT', 'JSONB_BUILD_ARRAY', 'JSONB_ARRAY_LENGTH',
    'HAS', 'APPEND', 'FIRST', 'UNIQUE', 'INTERSECTION',
    'SQRT', 'ABS', 'L2_DISTANCE', 'COSINE_SIMILARITY', 'APPROX_NEAR_L2', 'DISTANCE',

    # --- DuckDB 特有函数 ---
    'JSON_EXTRACT', 'JSON_CONTAINS', 'JSON_OBJECT', 'JSON_ARRAY_LENGTH',
    'UNNEST', 'LIST', 'LIST_APPEND', 'LIST_CONTAINS',
    'ARRAY', 'ARRAY_DISTANCE',
    
    # --- 常见数据类型(sql强制类型转换中要用到，算做操作符) ---
    'INT','FLOAT','JSON','TEXT','STRING','BOOL','JSONB'
}

# ==========================================
# 1b. Python 专用关键字（仅 .py 文件追加）
# ==========================================
PYTHON_EXTRA_KEYWORDS = {
    # --- Python 关键字 ---
    'DEF', 'CLASS', 'IF', 'ELIF', 'ELSE', 'FOR', 'WHILE', 'BREAK', 'CONTINUE',
    'TRY', 'EXCEPT', 'FINALLY', 'WITH', 'AS', 'IMPORT', 'FROM', 'RETURN', 'YIELD',
    'LAMBDA', 'PASS', 'RAISE', 'ASSERT', 'DEL', 'GLOBAL', 'NONLOCAL',
    'AND', 'OR', 'NOT', 'IN', 'IS', 'ASYNC', 'AWAIT',

    # --- Python 常用内置函数 ---
    'LEN', 'RANGE', 'ENUMERATE', 'ZIP', 'MAP', 'FILTER', 'REDUCE',
    'STR', 'INT', 'FLOAT', 'LIST', 'DICT', 'TUPLE', 'SET', 'BOOL',
    'PRINT', 'FORMAT', 'OPEN', 'ISINSTANCE', 'HASATTR', 'GETATTR',

    # --- Pandas/Polystore 常用方法 ---
    'DATAFRAME', 'SERIES', 'MERGE', 'JOIN', 'GROUPBY', 'AGG', 'APPLY',
    'SORT_VALUES', 'RESET_INDEX', 'DROP_DUPLICATES', 'FILLNA', 'DROPNA',
    'TO_DICT', 'TO_LIST', 'TO_SQL', 'READ_SQL',

    # --- MongoDB 聚合操作符 ($开头) ---
    '$LOOKUP', '$MATCH', '$GROUP', '$SORT', '$LIMIT', '$SKIP', '$UNWIND',
    '$PROJECT', '$COUNT', '$SUM', '$AVG', '$MIN', '$MAX', '$PUSH', '$ADDTOSET',
    '$FIRST', '$LAST', '$EXISTS', '$NE', '$EQ', '$GT', '$GTE', '$LT', '$LTE',
    '$IN', '$NIN', '$AND', '$OR', '$NOT', '$REGEX', '$TYPE', '$SIZE',
    '$COND', '$IFNULL', '$ARRAYELEMAT', '$SLICE', '$FILTER', '$MAP',
    '$REDUCE', '$MERGEOBJECTS', '$REPLACEWITH', '$SET',
    '$UNSET', '$ADDFIELDS', '$FACET', '$BUCKET', '$BUCKETAUTO',
    '$GEO', '$NEAR', '$GEONEAR', '$TEXT', '$SEARCH',
}

PYTHON_KEYWORDS = BASE_KEYWORDS | PYTHON_EXTRA_KEYWORDS


def _get_keywords(file_ext: str) -> set:
    if file_ext == '.py':
        return PYTHON_KEYWORDS
    else:
        return BASE_KEYWORDS

# ==========================================
# 2. Python 函数提取器
# ==========================================
def extract_function_by_name(py_code: str, func_name: str) -> str:
    try:
        tree = ast.parse(py_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                start_line = node.body[0].lineno - 1
                end_line = node.end_lineno
                lines = py_code.split('\n')
                func_lines = lines[start_line:end_line]
                cleaned_lines = [
                    line for line in func_lines
                    if 'TimerPhase' not in line
                ]
                return '\n'.join(cleaned_lines)
        return py_code
    except SyntaxError:
        return py_code


# ==========================================
# 3. 字符串智能处理
# ==========================================

_PY_STRING_RE = re.compile(
    r'[fFrRbBuU]{0,2}"""[\s\S]*?"""|'
    r"[fFrRbBuU]{0,2}'''[\s\S]*?'''|"
    r'[fFrRbBuU]{0,2}"(?:[^"\\]|\\.)*"|'
    r"[fFrRbBuU]{0,2}'(?:[^'\\]|\\.)*'"
)

_IDENT_LIKE_RE = re.compile(r'^[\w$][\w.$]*$')


def _build_string_replacer():
    seen = {}
    counter = [0]

    def replace(content: str) -> str:
        if content not in seen:
            seen[content] = f'_STRLIT_{counter[0]}_'
            counter[0] += 1
        return seen[content]

    return replace


def _strip_py_quotes(literal: str) -> str:
    s = literal
    while s and s[0].lower() in 'frbu':
        s = s[1:]
    for q in ('"""', "'''", '"', "'"):
        if s.startswith(q) and s.endswith(q) and len(s) >= 2 * len(q):
            return s[len(q):-len(q)]
    return s


def _first_word_is_keyword(text: str) -> bool:
    m = re.search(r'[A-Za-z_]\w*', text)
    return m is not None and m.group(0).upper() in BASE_KEYWORDS


def _clean_embedded_comments(content: str) -> str:
    content = re.sub(r'/\*.*?\*/', ' ', content, flags=re.S)
    content = re.sub(r'--.*$',     ' ', content, flags=re.M)
    content = re.sub(r'//.*$',     ' ', content, flags=re.M)
    return content


def _classify_string_content(content: str, is_python: bool, str_replacer) -> str:
    stripped = content.strip()
    if not stripped:
        return str_replacer('')
    if stripped.startswith('$'):
        return stripped
    if is_python:
        if _first_word_is_keyword(stripped):
            cleaned = _clean_embedded_comments(content)
            return ' ' + cleaned + ' '
        if _IDENT_LIKE_RE.match(stripped):
            return stripped
    return str_replacer(content)


def _process_python_strings_and_comments(source: str) -> str:
    saved: list[str] = []
    str_replacer = _build_string_replacer()

    def _save(m):
        saved.append(m.group(0))
        return f' __PYSTR_{len(saved) - 1}__ '

    code = _PY_STRING_RE.sub(_save, source)
    code = re.sub(r'#.*$', '', code, flags=re.M)

    def _restore(m):
        idx = int(m.group(1))
        inner = _strip_py_quotes(saved[idx])
        return ' ' + _classify_string_content(inner, True, str_replacer) + ' '

    code = re.sub(r'__PYSTR_(\d+)__', _restore, code)
    code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.S)
    return code


# ==========================================
# 4. 核心分析函数
# ==========================================
def analyze_multimodel_code(code_str: str, file_ext: str = '.sql', func_name: str = ''):

    if file_ext == '.py':
        code_str = extract_function_by_name(code_str, func_name)

    if file_ext == '.py':
        code = _process_python_strings_and_comments(code_str)
    else:
        code = re.sub(r'/\*.*?\*/', ' ', code_str, flags=re.S)
        code = re.sub(r'--.*$', '', code, flags=re.M)
        code = re.sub(r'//.*$', '', code, flags=re.M)

        str_replacer = _build_string_replacer()

        def repl_quote(m):
            content = m.group(1) if m.group(1) is not None else m.group(2)
            if not content:
                return str_replacer('')
            return _classify_string_content(content, False, str_replacer)

        code = re.sub(r"'([^']*)'|\"([^\"]*)\"", repl_quote, code)

    keywords = _get_keywords(file_ext)

    base_op_pattern = (
        r'::|->>|->|#>>|#>|@>|<@|\|\||&&|\?\&|\?\||'
        r'<->|<=>|<#>|'
        r'\.\.|'
        r'!=|<>|<=|>=|==|'
        r'->|<-'
    )
    python_op_pattern = (
        r'\*\*|//|<<|>>|:=|'
        r'\+=|-=|\*=|/=|//=|%=|@=|&=|\|=|\^=|>>=|<<=|\*\*='
    )

    if file_ext == '.py':
        OP_PATTERN = f'{base_op_pattern}|{python_op_pattern}'
    else:
        OP_PATTERN = base_op_pattern

    EXCLUDED_DELIMITERS = {',', ';'}

    TOKEN_RE = re.compile(
        f'({OP_PATTERN})' +
        r'|(\$\w+)' +
        r'|(\d+\.\d+|\d+)' +
        r'|(\b\w+\b)' +
        r'|([^\w\s])',
        re.IGNORECASE
    )

    operators = []
    operands = []

    for op, dollar, num, word, sgl in TOKEN_RE.findall(code):
        token = op or dollar or num or word or sgl
        if not token or token.strip() == '':
            continue
        if op:
            operators.append(op)
        elif dollar:
            upper = dollar.upper()
            if upper in keywords:
                operators.append(upper)
            else:
                operands.append(dollar)
        elif num:
            operands.append(num)
        elif word:
            upper = word.upper()
            if upper in keywords:
                if upper != 'BY':
                    operators.append(upper)
            else:
                operands.append(word)
        elif sgl:
            if sgl not in EXCLUDED_DELIMITERS:
                operators.append(sgl)

    n1 = len(set(operators))
    n2 = len(set(operands))
    N1 = len(operators)
    N2 = len(operands)

    if n2 == 0:
        n2 = 1

    vocabulary = n1 + n2
    length = N1 + N2
    volume = length * math.log2(vocabulary) if vocabulary > 0 else 0
    difficulty = (n1 / 2) * (N2 / n2)
    effort = difficulty * volume

    return {
        "n1": n1,
        "n2": n2,
        "N1": N1,
        "N2": N2,
        "Vocab": vocabulary,
        "Length": length,
        "Vol": round(volume, 2),
        "Diff": round(difficulty, 2),
        "Effort": round(effort, 2),
    }


def print_summary(results, metrics):
    if not results:
        return
    print("\n" + "=" * 80)
    print(f"{'Metric':<10} | {'Max':<10} | {'Median':<10} | {'Avg':<10} | {'StdDev':<10}")
    print("-" * 60)
    summary_data = {}
    for m in metrics:
        values = [r[m] for r in results]
        max_val = max(values)
        med_val = statistics.median(values)
        avg_val = statistics.mean(values)
        std_val = statistics.stdev(values) if len(values) > 1 else 0.0
        summary_data[m] = {'Max': max_val, 'Median': med_val, 'Avg': avg_val, 'StdDev': std_val}
        print(f"{m:<10} | {max_val:<10.1f} | {med_val:<10.1f} | {avg_val:<10.1f} | {std_val:<10.1f}")
    print("=" * 80 + "\n")
    return summary_data


def main():
    parser = argparse.ArgumentParser(
        description="Calculate Halstead Complexity Metrics for Multi-model Queries (SQL/AQL/Python)"
    )
    parser.add_argument("input_dir", help="Directory containing .sql, .aql, or .py files")
    parser.add_argument("-o", "--output", default="complexity_report.csv", help="Output CSV filename")
    parser.add_argument("-x", "--exclude", nargs='*', default=[],
                        help="List of filenames to exclude")

    args = parser.parse_args()
    input_path = Path(args.input_dir)
    if not input_path.is_dir():
        print(f"Error: Directory not found -> {args.input_dir}")
        sys.exit(1)

    raw_files = []
    for ext in ['*.sql', '*.aql', '*.py']:
        raw_files.extend(list(input_path.glob(ext)))

    exclude_set = set(args.exclude)
    if exclude_set:
        print(f"Excluding {len(exclude_set)} files: {exclude_set}")

    files = sorted([f for f in raw_files if f.name not in exclude_set])

    if not files:
        print(f"No files found in {args.input_dir} (after exclusion)")
        sys.exit(0)

    print(f"Found {len(files)} files. Analyzing...")
    print(f"{'File':<20} | {'Effort':<10} | {'Diff':<6} | {'n1':<4} | {'n2':<4}")
    print("-" * 60)

    results = []
    for f in files:
        try:
            content = f.read_text(encoding='utf-8')
            file_ext = f.suffix.lower()
            func_name = f.stem
            metrics = analyze_multimodel_code(content, file_ext=file_ext, func_name=func_name)
            metrics_with_name = {'File': f.name}
            metrics_with_name.update(metrics)
            results.append(metrics_with_name)
            print(
                f"{f.name:<20} | {metrics['Effort']:<10.1f} | {metrics['Diff']:<6.1f} | "
                f"{metrics['n1']:<4} | {metrics['n2']:<4}"
            )
        except Exception as e:
            print(f"Error processing {f.name}: {e}")

    target_metrics = ['n1', 'n2', 'N1', 'N2', 'Vocab', 'Length', 'Vol', 'Diff', 'Effort']
    summary = print_summary(results, target_metrics)

    if results:
        headers = ['File'] + target_metrics
        try:
            with open(args.output, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                writer.writerows(results)
                writer.writerow({})
                writer.writerow({'File': '=== SUMMARY ==='})
                row_max = {'File': 'Max'}
                for m in target_metrics:
                    row_max[m] = round(summary[m]['Max'], 2)
                writer.writerow(row_max)
                row_med = {'File': 'Median'}
                for m in target_metrics:
                    row_med[m] = round(summary[m]['Median'], 2)
                writer.writerow(row_med)
                row_avg = {'File': 'Avg'}
                for m in target_metrics:
                    row_avg[m] = round(summary[m]['Avg'], 2)
                writer.writerow(row_avg)
                row_std = {'File': 'StdDev'}
                for m in target_metrics:
                    row_std[m] = round(summary[m]['StdDev'], 2)
                writer.writerow(row_std)
            print(f"Successfully saved report to: {args.output}")
        except IOError as e:
            print(f"\nError writing CSV file: {e}")


if __name__ == "__main__":
    main()
