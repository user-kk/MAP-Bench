#!/usr/bin/env python3
"""
多数据库 token / 节点 汇总器
用法示例：
    # 默认读取脚本内 DEFAULT_DBS
    python3 compare_token.py -f markdown -o report.md

    # 命令行显式指定
    python3 compare_token.py \
        --db helmdb=./helmdb.csv \
        --db duckdb=./duckdb.csv \
        -f csv -o report.csv
"""
from __future__ import annotations
import argparse
import csv
import datetime
import pathlib
import sys
from collections import Counter, OrderedDict
from typing import Dict, List, Tuple

import pandas as pd

# ---------- 1. 默认配置 ----------
ROOT_PATH = '/home/hyh/OpenAlex_mini_new/'
DEFAULT_DBS: "OrderedDict[str, pathlib.Path]" = OrderedDict(
    [
        ("helmdb", ROOT_PATH + "script/helmdb/query/out/info_2025-12-05_18:24:11.csv"),
        ("arangodb", ROOT_PATH + "script/arangodb/query/out/info_2025-12-05_18:18:31.csv"),
        ("agensgraph", ROOT_PATH + "script/agensgraph/query/out/info_2025-12-05_18:18:47.csv"),
        ("duckdb", ROOT_PATH + "script/duckdb/query/out/info_2025-12-05_18:20:32.csv"),
    ]
)


# ---------- 2. 工具函数 ----------
def parse_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="汇总多份 csv 的 token / 节点指标")
    p.add_argument(
        "--db",
        action="append",
        default=[],
        help="显式指定数据库名与路径，格式 名称=路径，可多次使用",
    )
    p.add_argument(
        "-o", "--output", help="输出文件路径；缺省生成 compare_<时间戳>.[csv|md]"
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
def _parse_ops(ops_cell: str) -> Counter:
    """把 'CalculationNode:13,SortNode:4,...' 解析成 Counter"""
    if not ops_cell.strip():
        return Counter()
    return Counter(
        {
            part.split(":")[0].strip(): int(part.split(":")[1])
            for part in ops_cell.split(",")
            if ":" in part
        }
    )


def load_csv(path: pathlib.Path) -> pd.DataFrame:
    """读入单份 csv，返回标准化后的 DataFrame"""
    rows = []
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            file_raw = r["file"].strip()
            if not file_raw:
                continue
            qtype = pathlib.Path(file_raw).stem.split(".")[0][
                0
            ]  # A1 -> A, G2 -> G ...
            tokens = int(r["tokens"])
            nodes = int(r["nodes"])
            ops = _parse_ops(r["ops"])
            rows.append(
                {
                    "db": path.stem.split("_")[0],
                    "query": pathlib.Path(file_raw).stem,
                    "qtype": qtype,
                    "tokens": tokens,
                    "nodes": nodes,
                    "ops": ops,
                }
            )
    return pd.DataFrame(rows)


# ---------- 4. 汇总 ----------
def _agg(df: pd.DataFrame) -> pd.Series:
    """对子表计算所需指标"""
    return pd.Series(
        {
            "avg_tokens": df["tokens"].mean(),
            "var_tokens": df["tokens"].var(ddof=0),
            "max_tokens": df["tokens"].max(),
            "avg_nodes": df["nodes"].mean(),
            "max_nodes": df["nodes"].max(),
            "var_nodes": df["nodes"].var(ddof=0),
            "top5_ops": (
                sum(df["ops"], Counter()).most_common(5)  # type: ignore
            ),
        }
    )


def build_summary(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """返回 (全局汇总, 分组汇总) 两张表"""
    global_df = df.groupby("db").apply(_agg, include_groups=False).reset_index()
    group_df = (
        df.groupby(["db", "qtype"])
        .apply(_agg, include_groups=False)
        .reset_index()
        .sort_values(["qtype", "db"])     
    )
    return global_df, group_df


# ---------- 5. 输出 ----------
def _fmt_ops(ops: List[Tuple[str, int]]) -> str:
    return ", ".join(f"{n}({c})" for n, c in ops)


def to_markdown(df: pd.DataFrame) -> str:
    """转 markdown 表格"""
    cols = [c for c in df.columns if c != "top5_ops"] + ["top5_ops"]
    lines = ["| " + " | ".join(cols) + " |"]
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in df.iterrows():
        line = [
            f"{row[c]:.1f}" if isinstance(row[c], float) else str(row[c])
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
        global_df.to_csv(global_out, index=False, float_format="%.2f")
        group_df.to_csv(group_out, index=False, float_format="%.2f")
        print(f"已生成 {global_out}  {group_out}")


# ---------- 6. 主流程 ----------
def main():
    args = parse_cli()
    db_map = build_db_map(args)
    ext = "md" if args.format in ("md", "markdown") else "csv"
    out_path = pathlib.Path(
        args.output or f"compare_token_{datetime.datetime.now():%Y%m%d_%H%M%S}.{ext}"
    )

    # 读取
    df_parts = []
    for name, path in db_map.items():
        part = load_csv(path)
        part["db"] = name
        df_parts.append(part)
    df = pd.concat(df_parts, ignore_index=True)

    # 汇总
    global_df, group_df = build_summary(df)

    # 输出
    write(global_df, group_df, args.format, out_path)
    print(f"已生成 {out_path.absolute()}")


if __name__ == "__main__":
    main()