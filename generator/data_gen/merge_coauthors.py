import argparse
import csv
import json
import os
import sys
from pathlib import Path
from tqdm import tqdm

csv.field_size_limit(sys.maxsize)

def merge_author_collaborations(input_file, output_file):
    if not os.path.exists(input_file):
        print(f" ERROR: 找不到输入文件 {input_file}")
        return

    print("========== 开始合并作者合作边 ==========")
    print(f"  输入文件: {input_file}")
    print(f"  输出文件: {output_file}")

    print("\n[1/3] 正在加载边表...")
    with open(input_file, "r", encoding="utf-8") as fin:
        reader = csv.reader(fin)
        header = next(reader)
        all_rows = list(reader)

    print(f"      加载完成，共读取 {len(all_rows):,} 条边。")

    merged_data = {}
    for row in tqdm(all_rows, desc="[2/3] 聚合边", unit="边", colour="green"):
        if len(row) < 3:
            continue

        u_str, v_str, props_str = row[0], row[1], row[2]
        if int(u_str) > int(v_str):
            u_str, v_str = v_str, u_str

        edge_key = (u_str, v_str)
        if edge_key not in merged_data:
            merged_data[edge_key] = {"cnt": 0, "list": []}

        try:
            props = json.loads(props_str)
        except json.JSONDecodeError:
            continue

        merged_data[edge_key]["cnt"] += props.get("cnt", 1)
        if "list" in props and isinstance(props["list"], list):
            merged_data[edge_key]["list"].extend(props["list"])

    original_edges_count = len(all_rows)
    del all_rows

    unique_edges_count = len(merged_data)
    compression_ratio = unique_edges_count / (original_edges_count + 1e-9) * 100
    print(f"      聚合完成，得到 {unique_edges_count:,} 条去重边。")
    print(f"      压缩率: {compression_ratio:.2f}%")

    print("\n[3/3] 正在写入结果...")
    with open(output_file, "w", encoding="utf-8", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(header)
        for (u, v), props in tqdm(merged_data.items(), desc="      写入边", unit="边", colour="blue"):
            writer.writerow([u, v, json.dumps(props)])

    print("\n========== 合并完成 ==========")

def parse_args():
    script_dir = Path(__file__).resolve().parent
    generator_root = script_dir.parent
    default_generated_root = Path(
        os.environ.get(
            "MAP_BENCH_GENERATED_ROOT_DIR",
            str(generator_root / "generated_output"),
        )
    )

    parser = argparse.ArgumentParser(description="合并作者合作多重边")
    parser.add_argument(
        "--graph-edges-dir",
        type=Path,
        default=default_generated_root / "sf_2_mode_1" / "graph_edges",
        help="graph_edges 目录路径",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="输入文件路径，默认是 <graph-edges-dir>/authors_authors_e.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出文件路径，默认是 <graph-edges-dir>/authors_authors_e_merged.csv",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    input_csv = args.input or (args.graph_edges_dir / "authors_authors_e.csv")
    output_csv = args.output or (args.graph_edges_dir / "authors_authors_e_merged.csv")
    merge_author_collaborations(str(input_csv), str(output_csv))
