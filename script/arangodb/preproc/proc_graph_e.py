#!/usr/bin/env python3
"""
把带嵌套 JSON 字段的 CSV 文件批量转成 JSONL。
示例：
    python proc_graph_v.py input.csv -o output.jsonl -b 50000
"""
import argparse
import csv
import json
import pathlib
import sys


def csv_to_jsonl(csv_path,
                 jsonl_path,
                 from_table,
                 to_table,
                 batch_size = 100_000
                ) -> None:
    jsonl_path = jsonl_path or csv_path.with_suffix(".jsonl")
    row_cnt = 0

    with csv_path.open(newline="", encoding="utf-8") as fin, \
         jsonl_path.open("w", encoding="utf-8") as fout:

        reader = csv.DictReader(fin)
        batch: list[dict] = []

        for row in reader:
            # 1. 把原始 JSON 字符串解析成 dict
            try:
                raw_doc = json.loads(row.pop("properties"))
            except (KeyError, json.JSONDecodeError) as e:
                print(f"跳过坏行 #{reader.line_num}: {e}", file=sys.stderr)
                continue

            # 2. 组装新结构：
            new_rec = {
                "_from": from_table+'/'+row["startid"],
                "_to": to_table+'/'+row["endid"],
                **raw_doc
            }

            batch.append(new_rec)

            if len(batch) >= batch_size:
                fout.write("".join(json.dumps(rec, ensure_ascii=False) + "\n"
                                   for rec in batch))
                row_cnt += len(batch)
                batch.clear()

        if batch:
            fout.write("".join(json.dumps(rec, ensure_ascii=False) + "\n"
                               for rec in batch))
            row_cnt += len(batch)

    print(f"完成！共 {row_cnt} 条 -> {jsonl_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将嵌套 JSON 字段的 CSV 转换为 JSONL，支持批量写入。")
    parser.add_argument("csv",
                        type=pathlib.Path,
                        help="输入 CSV 文件路径")
    parser.add_argument("-o", "--output",
                        type=pathlib.Path,
                        dest="jsonl",
                        help="输出 JSONL 文件路径（默认：同目录下同名校准 .jsonl）")
    parser.add_argument("-b", "--batch",
                        type=int,
                        default=100_000,
                        help="每批写入行数（默认：100000）")
    parser.add_argument("--from", "--from",
                        dest='from_table',
                        type=str,
                        required=True,
                        help="from表名")
    parser.add_argument("--to", "--to",
                        dest='to_table',
                        type=str,
                        required=True,
                        help="to表名")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    csv_to_jsonl(args.csv, args.jsonl, args.from_table,args.to_table,args.batch)