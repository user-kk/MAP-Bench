#!/usr/bin/env python3
import re
import math
import csv
import argparse
import sys
import statistics
from pathlib import Path

# ==========================================
# 1. 统一关键字库 (SQL + Cypher + AQL + FleetDB + DuckDB)
# ==========================================
UNIFIED_KEYWORDS = {
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
    
    # --- Functions (Postgres / DuckDB Native) ---
    'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COUNT_DISTINCT', 
    'LENGTH', 'CONCAT', 'TO_STRING', 'TO_NUMBER', 'TO_JSONB', 'SUBSTRING', 'FLOOR', 
    'COALESCE', 'JSONB_ARRAY_ELEMENTS', 'JSONB_PATH_QUERY_ARRAY', 'JSON_AGG', 'ARRAY_AGG',
    'JSONB_BUILD_OBJECT', 'JSONB_BUILD_ARRAY', 'JSONB_ARRAY_LENGTH', 
    'HAS', 'APPEND', 'FIRST', 'UNIQUE', 'INTERSECTION',
    'SQRT', 'ABS', 'L2_DISTANCE', 'COSINE_SIMILARITY', 'APPROX_NEAR_L2', 'DISTANCE',
    
    # --- [新增] DuckDB 特有函数 ---
    'JSON_EXTRACT', 'JSON_CONTAINS', 'JSON_OBJECT', 'JSON_ARRAY_LENGTH', 
    'UNNEST', 'LIST', 'LIST_APPEND', 'LIST_CONTAINS', 
    'ARRAY', 'ARRAY_DISTANCE' 
}

# ==========================================
# 2. 保留的结构化字符串 (白名单)
# ==========================================
KEEP_STRINGS = {
    'work_author_gra', 'work_topic_gra', 'author_author_gra', 'work_work_gra',
    'author_v', 'work_v', 'topic_v', 'work_author_e', 'work_topic_e', 
    'author_author_e', 'work_referenced_work_e',
    'academic_net'
}

def analyze_multimodel_code(code_str: str):
    
    # Step 1: 暴力去注释
    code = re.sub(r'/\*.*?\*/', ' ', code_str, flags=re.S)
    code = re.sub(r'--.*$', '', code, flags=re.M)
    code = re.sub(r'//.*$', '', code, flags=re.M)
    
    # Step 2: 字符串归一化
    def repl_quote(m):
        content = m.group(1) if m.group(1) is not None else m.group(2)
        if not content: return '""'
        if content.startswith('$') or content in KEEP_STRINGS:
            return content
        return 'STR'

    code = re.sub(r"""'([^']*)'|"([^"]*)\" """, repl_quote, code)

    # Step 3: 分词
    OP_PATTERN = (
        r'::|->>|->|#>>|#>|@>|<@|\|\||&&|\?\&|\?\||'      
        r'<->|<=>|<#>|'                                   
        r'\.\.|'                                          
        r'!=|<>|<=|>=|==|'                                
        r'->|<-'                                          
    )
    
    TOKEN_RE = re.compile(
        f'({OP_PATTERN})' +           
        r'|(\d+\.\d+|\d+)' +          
        r'|(\b\w+\b)' +               
        r'|([^\w\s])',                
        re.IGNORECASE
    )

    operators = []
    operands = []
    
    for op, num, word, sgl in TOKEN_RE.findall(code):
        token = op or num or word or sgl
        if not token or token.strip() == '': continue
        
        if op:
            operators.append(op)
        elif sgl:
            operators.append(sgl)
        elif word:
            upper = word.upper()
            if upper in UNIFIED_KEYWORDS:
                operators.append(upper)
            else:
                operands.append(word)
        elif num:
            operands.append(num)

    # Step 4: Halstead 计算
    n1 = len(set(operators))
    n2 = len(set(operands))
    N1 = len(operators)
    N2 = len(operands)
    
    if n2 == 0: n2 = 1 
    
    vocabulary = n1 + n2
    length = N1 + N2
    volume = length * math.log2(vocabulary) if vocabulary > 0 else 0
    difficulty = (n1 / 2) * (N2 / n2)
    effort = difficulty * volume
    
    return {
        # 1. 基础计数
        "n1": n1,       
        "n2": n2,       
        "N1": N1,       
        "N2": N2,       
        
        # 2. 核心比率
        "Reuse": round(N2/n2, 2) if n2 > 0 else 0,
        "Vocab": vocabulary,
        "Length": length,
        
        # 3. Halstead 高级指标
        "Vol": round(volume, 2),
        "Diff": round(difficulty, 2),
        "Effort": round(effort, 2)
    }

def print_summary(results, metrics):
    """计算并打印统计汇总"""
    if not results: return
    
    print("\n" + "="*80)
    print(f"{'Metric':<10} | {'Max':<10} | {'Avg':<10} | {'StdDev':<10}")
    print("-" * 50)
    
    summary_data = {}
    
    for m in metrics:
        values = [r[m] for r in results]
        max_val = max(values)
        avg_val = statistics.mean(values)
        std_val = statistics.stdev(values) if len(values) > 1 else 0.0
        
        summary_data[m] = {'Max': max_val, 'Avg': avg_val, 'StdDev': std_val}
        print(f"{m:<10} | {max_val:<10.1f} | {avg_val:<10.1f} | {std_val:<10.1f}")
        
    print("="*80 + "\n")
    return summary_data

def main():
    parser = argparse.ArgumentParser(description="Calculate Halstead Complexity Metrics for Multi-model Queries")
    parser.add_argument("input_dir", help="Directory containing .sql or .aql files")
    parser.add_argument("-o", "--output", default="complexity_report.csv", help="Output CSV filename")
    # 新增排除参数，nargs='*' 表示可以接受多个值
    parser.add_argument("-x", "--exclude", nargs='*', default=[], help="List of filenames to exclude (e.g. -x A1.sql G1.aql)")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_dir)
    if not input_path.is_dir():
        print(f"Error: Directory not found -> {args.input_dir}")
        sys.exit(1)
        
    # 获取原始文件列表
    raw_files = list(input_path.glob("*.sql")) + list(input_path.glob("*.aql"))
    
    # 构建排除集合 (文件名)
    exclude_set = set(args.exclude)
    if exclude_set:
        print(f"Excluding {len(exclude_set)} files: {exclude_set}")
    
    # 过滤文件
    files = sorted([f for f in raw_files if f.name not in exclude_set])
    
    if not files:
        print(f"No files found in {args.input_dir} (after exclusion)")
        sys.exit(0)
        
    print(f"Found {len(files)} files. Analyzing...")
    print(f"{'File':<20} | {'Effort':<10} | {'Diff':<6} | {'Reuse':<6} | {'n1':<4} | {'n2':<4}")
    print("-" * 75)
    
    results = []
    
    for f in files:
        try:
            content = f.read_text(encoding='utf-8')
            metrics = analyze_multimodel_code(content)
            metrics_with_name = {'File': f.name}
            metrics_with_name.update(metrics)
            results.append(metrics_with_name)
            
            print(f"{f.name:<20} | {metrics['Effort']:<10.1f} | {metrics['Diff']:<6.1f} | {metrics['Reuse']:<6.1f} | {metrics['n1']:<4} | {metrics['n2']:<4}")
            
        except Exception as e:
            print(f"Error processing {f.name}: {e}")

    # 计算汇总
    target_metrics = ['n1', 'n2', 'N1', 'N2', 'Reuse', 'Vocab', 'Length', 'Vol', 'Diff', 'Effort']
    summary = print_summary(results, target_metrics)

    # 写入 CSV
    if results:
        headers = ['File'] + target_metrics
        
        try:
            with open(args.output, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                writer.writerows(results)
                
                # 写入汇总数据
                writer.writerow({}) # 空行
                writer.writerow({'File': '=== SUMMARY ==='})
                
                # Max 行
                row_max = {'File': 'Max'}
                for m in target_metrics: row_max[m] = round(summary[m]['Max'], 2)
                writer.writerow(row_max)
                
                # Avg 行
                row_avg = {'File': 'Avg'}
                for m in target_metrics: row_avg[m] = round(summary[m]['Avg'], 2)
                writer.writerow(row_avg)
                
                # StdDev 行
                row_std = {'File': 'StdDev'}
                for m in target_metrics: row_std[m] = round(summary[m]['StdDev'], 2)
                writer.writerow(row_std)

            print(f"Successfully saved report to: {args.output}")
            
        except IOError as e:
            print(f"\nError writing CSV file: {e}")

if __name__ == "__main__":
    main()