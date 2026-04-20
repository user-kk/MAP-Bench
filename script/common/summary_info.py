#!/usr/bin/env python3
"""
多数据库 token / 节点 汇总器
支持两种格式：
1. 传统格式：file, tokens, nodes, ops（查询计划统计）
2. Polyglot格式：file, tokens, breakdown（模型运行时间占比）

用法示例：
    python3 compare_token.py --db polyglot=./polyglot.csv -f md -o report.md
"""
from __future__ import annotations
import argparse
import csv
import datetime
import pathlib
import sys
import re
from collections import Counter, OrderedDict, defaultdict
from typing import Dict, List, Tuple, Optional
import pandas as pd

# ---------- 1. 默认配置 ----------
ROOT_PATH = '/home/hyh/OpenAlex_mini_new/'
DEFAULT_DBS: "OrderedDict[str, pathlib.Path]" = OrderedDict(
    [
        ("gredodb", ROOT_PATH + "script/gredodb/query/out/info_2026-03-16_19:09:49.csv"),
        ("arangodb", ROOT_PATH + "script/arangodb/query/out/info_2026-03-16_19:07:15.csv"),
        ("agensgraph", ROOT_PATH + "script/agensgraph/query/out/info_2026-03-16_19:06:23.csv"),
        ("duckdb", ROOT_PATH + "script/duckdb/query/out/info_2026-03-16_19:09:19.csv"),
        ("polystore", ROOT_PATH + "script/polystore/query/out/info_2026-03-22_16:35:50.csv"),
    ]
)


# ---------- 2. 工具函数 ----------
def parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="汇总多份 csv 的 token / 节点 / 模型指标")
    p.add_argument(
        "--db",
        action="append",
        default=[],
        help="显式指定数据库名与路径，格式 名称=路径，可多次使用",
    )
    p.add_argument(
        "-o", "--output", help="输出文件路径；缺省生成 out/compare_<时间戳>.[csv|md]"
    )
    p.add_argument(
        "-f",
        "--format",
        choices=["csv", "md", "markdown"],
        default="csv",
        help="输出格式：csv（默认）或 markdown",
    )
    return p.parse_args()


def build_db_map(args: argparse.Namespace) -> "OrderedDict[str, pathlib.Path]":
    """合并三种来源，返回有序字典"""
    db_map: "OrderedDict[str, pathlib.Path]" = OrderedDict()

    # 1. 命令行 --db
    for item in args.db:
        if "=" not in item:
            print(f"--db 参数格式错误：{item}", file=sys.stderr)
            sys.exit(1)
        name, path = item.split("=", 1)
        db_map[name.strip()] = pathlib.Path(path.strip())

    # 2. 脚本内默认
    for name, path in DEFAULT_DBS.items():
        if name not in db_map and pathlib.Path(path).exists():
            db_map[name] = pathlib.Path(path)

    if not db_map:
        print("未找到任何有效 csv，请通过 --db 或 DEFAULT_DBS 指定", file=sys.stderr)
        sys.exit(1)
    return db_map


# ---------- 3. 读取与解析 ----------
def _parse_ops_counts(ops_cell: str) -> Counter:
    """解析算子出现次数"""
    if not ops_cell.strip():
        return Counter()
    return Counter({
        part.split(":")[0].strip(): int(part.split(":")[1])
        for part in ops_cell.split(",")
        if ":" in part
    })


def _parse_ops(ops_cell: str) -> Tuple[Counter, Counter]:
    """
    解析算子信息，返回(次数Counter, 百分比Counter)
    """
    if not ops_cell.strip():
        return Counter(), Counter()
    
    count_counter = _parse_ops_counts(ops_cell)
    total = sum(count_counter.values())
    if total == 0:
        return count_counter, Counter()
    
    pct_counter = Counter({
        op: (count / total * 100)
        for op, count in count_counter.items()
    })
    
    return count_counter, pct_counter


def _parse_breakdown(breakdown_cell: str) -> Counter:
    """解析 polyglot 的 breakdown 列，返回模型占比 Counter"""
    if not breakdown_cell.strip():
        return Counter()
    
    share_counter = Counter()
    pattern = r'(\w+):\d+\.?\d*ms\((\d+\.?\d*)%\)'
    matches = re.findall(pattern, breakdown_cell)
    
    for model, share in matches:
        try:
            share_counter[model] = float(share)
        except ValueError:
            continue
    
    return share_counter


def detect_csv_format(path: pathlib.Path) -> str:
    """检测CSV格式类型"""
    with path.open(newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return "unknown"
        
        header_set = set(h.strip() for h in header)
        if "breakdown" in header_set:
            return "polyglot"
        elif "nodes" in header_set and "ops" in header_set:
            return "traditional"
        else:
            return "unknown"


def load_csv(path: pathlib.Path) -> pd.DataFrame:
    """读入单份 csv，返回标准化后的 DataFrame"""
    fmt = detect_csv_format(path)
    
    rows = []
    with path.open(newline="") as f:
        if fmt == "polyglot":
            for r in csv.DictReader(f):
                file_raw = r["file"].strip()
                if not file_raw:
                    continue
                qtype = pathlib.Path(file_raw).stem.split(".")[0][0]
                tokens = int(r["tokens"])
                ops_pct = _parse_breakdown(r["breakdown"])
                rows.append({
                    "qtype": qtype,
                    "tokens": tokens,
                    "nodes": float('nan'),
                    "ops_counts": None,
                    "ops_pct": ops_pct,
                    "format": fmt,
                })
        elif fmt == "traditional":
            for r in csv.DictReader(f):
                file_raw = r["file"].strip()
                if not file_raw:
                    continue
                qtype = pathlib.Path(file_raw).stem.split(".")[0][0]
                tokens = int(r["tokens"])
                nodes = int(r["nodes"])
                ops_counts, ops_pct = _parse_ops(r["ops"])
                rows.append({
                    "qtype": qtype,
                    "tokens": tokens,
                    "nodes": nodes,
                    "ops_counts": ops_counts,
                    "ops_pct": ops_pct,
                    "format": fmt,
                })
        else:
            print(f"警告：无法识别 {path} 的格式，跳过处理", file=sys.stderr)
            return pd.DataFrame()
    
    return pd.DataFrame(rows)


# ---------- 4. 汇总 ----------
def _agg(df: pd.DataFrame) -> pd.Series:
    """对子表计算所需指标"""
    fmt = df["format"].iloc[0] if "format" in df.columns else "traditional"
    is_polyglot = (fmt == "polyglot")
    
    if is_polyglot:
        # Polyglot：只统计平均占比
        shares = defaultdict(list)
        for counter in df["ops_pct"]:
            for key, value in counter.items():
                shares[key].append(value)
                
        query_count = len(df)  # ← 用总查询数
        avg_shares = {k: sum(v)/query_count for k, v in shares.items()}
        top5_ops = sorted(avg_shares.items(), key=lambda x: x[1], reverse=True)[:5]
        top5_ops = [(name, pct) for name, pct in top5_ops]
    else:
        # 传统格式：统计总次数和平均占比
        total_counts = defaultdict(int)
        pct_sums = defaultdict(float)
        
        for _, row in df.iterrows():
            count_counter = row["ops_counts"]
            if count_counter is None:
                continue
                
            pct_counter = row["ops_pct"]
            
            for op, count in count_counter.items():
                total_counts[op] += count
                pct_sums[op] += pct_counter[op]
        
        query_count = len(df)
        avg_shares = {op: pct_sums[op] / query_count for op in pct_sums}
        
        top5 = sorted(avg_shares.items(), key=lambda x: x[1], reverse=True)[:5]
        top5_ops = [(name, total_counts[name], pct) for name, pct in top5]
    
    # **修复：修改为 avg → var → max 顺序**
    result = {
        "avg_tokens": df["tokens"].mean(),
        "var_tokens": df["tokens"].var(ddof=0),
        "max_tokens": df["tokens"].max(),
        "avg_nodes": float('nan') if is_polyglot else df["nodes"].mean(),
        "var_nodes": float('nan') if is_polyglot else df["nodes"].var(ddof=0),
        "max_nodes": float('nan') if is_polyglot else df["nodes"].max(),
        "top5_ops": top5_ops,
    }
    
    return pd.Series(result)


def build_summary(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """返回 (全局汇总, 分组汇总) 两张表"""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    global_df = df.groupby("db").apply(_agg, include_groups=False).reset_index()
    group_df = (
        df.groupby(["db", "qtype"])
        .apply(_agg, include_groups=False)
        .reset_index()
        .sort_values(["qtype", "db"])
    )
    
    # **修复：列顺序改为 avg → var → max **
    global_cols = ["db", "avg_tokens", "var_tokens", "max_tokens", 
                   "avg_nodes", "var_nodes", "max_nodes", "top5_ops"]
    group_cols = ["db", "qtype"] + global_cols[ 2: ]  # 保持与global_cols一致的顺序
    
    global_df = global_df.reindex(columns=global_cols)
    group_df = group_df.reindex(columns=group_cols)
    
    return global_df, group_df


# ---------- 5. 输出 ----------
def _fmt_ops(ops: List[Tuple]) -> str:
    """
    格式化ops：
    - 传统格式：算子名(总次数, 平均占比%)
    - Polyglot格式：模型名(平均占比%)
    """
    if not ops:
        return ""
    
    parts = []
    for item in ops:
        if len(item) == 3:
            name, total_count, avg_pct = item
            parts.append(f"{name}({total_count}, {avg_pct:.2f}%)")
        elif len(item) == 2:
            name, avg_pct = item
            parts.append(f"{name}({avg_pct:.2f}%)")
    
    return ", ".join(parts)


def to_markdown(df: pd.DataFrame) -> str:
    """转 markdown 表格"""
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |"]
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in df.iterrows():
        line = [
            f"{row[c]:.2f}" if isinstance(row[c], float) and not pd.isna(row[c]) else 
            "N/A" if pd.isna(row[c]) else 
            str(row[c])
            for c in cols[:-1]
        ] + [_fmt_ops(row["top5_ops"])]
        lines.append("| " + " | ".join(line) + " |")
    return "\n".join(lines)


def write(global_df: pd.DataFrame, group_df: pd.DataFrame, fmt: str, out: pathlib.Path):
    if fmt in ("md", "markdown"):
        out.write_text(
            "## 全局汇总\n"
            + to_markdown(global_df)
            + "\n\n## 分组汇总（按查询种类）\n"
            + to_markdown(group_df),
            encoding="utf8",
        )
    else:
        # csv：拆成两个 sheet 不方便，直接两张表，文件名加后缀
        global_out = out.with_name(out.stem + "_global.csv")
        group_out = out.with_name(out.stem + "_group.csv")
        
        global_df_fmt = global_df.copy()
        group_df_fmt = group_df.copy()
        
        for df in [global_df_fmt, group_df_fmt]:
            if "top5_ops" in df.columns:
                df["top5_ops"] = df["top5_ops"].apply(_fmt_ops)
        
        # 保持列顺序输出
        global_df_fmt.to_csv(global_out, index=False, float_format="%.2f", 
                             columns=global_df.columns.tolist())
        group_df_fmt.to_csv(group_out, index=False, float_format="%.2f",
                            columns=group_df.columns.tolist())
        print(f"已生成 {global_out}  {group_out}")


# ---------- 6. 主流程 ----------
def main():
    args = parse_cli()
    db_map = build_db_map(args)
    ext = "md" if args.format in ("md", "markdown") else "csv"
    out_path = pathlib.Path(
        args.output or f"out/compare_token_{datetime.datetime.now():%Y%m%d_%H%M%S}.{ext}"
    )

    # 读取
    df_parts = []
    for name, path in db_map.items():
        print(f"正在加载: {name} ({path})")
        part = load_csv(path)
        if not part.empty:
            part["db"] = name
            df_parts.append(part)
    
    if not df_parts:
        print("错误：未成功加载任何数据文件", file=sys.stderr)
        sys.exit(1)
        
    df = pd.concat(df_parts, ignore_index=True)

    # 汇总
    print("正在生成汇总统计...")
    global_df, group_df = build_summary(df)
    

    # 输出
    write(global_df, group_df, args.format, out_path)
    print(f"已生成")


if __name__ == "__main__":
    main()