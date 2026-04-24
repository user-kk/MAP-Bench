import csv
import json
import os
import sys
import argparse
from pathlib import Path
from tqdm import tqdm

# 增加 CSV 字段大小限制，防止巨大 JSON 导致报错
csv.field_size_limit(sys.maxsize)

def merge_author_collaborations(input_file, output_file):
    if not os.path.exists(input_file):
        print(f" ERROR: 找不到输入文件 {input_file}")
        return

    print(f"========== 开始合并多重图 (全内存极速版) ==========")
    print(f"  输入文件: {input_file}")
    print(f"  输出文件: {output_file}")
    
    # ---------------------------------------------------------
    # 一次性全部读入内存 (得益于你的 256G 大内存)
    # ---------------------------------------------------------
    print("\n[1/3] 正在将整个边表加载进内存 (请稍候，由于没有 I/O 阻塞，这步会很快)...")
    with open(input_file, 'r', encoding='utf-8') as fin:
        reader = csv.reader(fin)
        header = next(reader) # 提取表头
        all_rows = list(reader) # 🌟 核心：一次性读取所有行到内存列表中
        
    print(f"      ✅ 加载完毕！共读取了 {len(all_rows):,} 条初始多重边。")

    # ---------------------------------------------------------
    # 全内存 Hash 聚合
    # ---------------------------------------------------------
    merged_data = {}
    
    # 使用 tqdm 包装列表，可以获得非常精准的进度和速度 (it/s)
    for row in tqdm(all_rows, desc="[2/3] 内存聚合中 (JSON 解析与合并)", unit="边", colour="green"):
        if len(row) < 3: 
            continue
            
        u_str, v_str, props_str = row[0], row[1], row[2]
        
        # 确保小 ID 在前，大 ID 在后（生成器里虽然做了，这里再上个保险）
        if int(u_str) > int(v_str):
            u_str, v_str = v_str, u_str
            
        edge_key = (u_str, v_str)
        
        # 初始化字典项
        if edge_key not in merged_data:
            merged_data[edge_key] = {"cnt": 0, "list": []}
            
        # 解析 JSON 并合并累加
        try:
            props = json.loads(props_str)
            merged_data[edge_key]["cnt"] += props.get("cnt", 1)
            
            if "list" in props and isinstance(props["list"], list):
                merged_data[edge_key]["list"].extend(props["list"])
        except json.JSONDecodeError:
            continue

    # 释放原始 List 的内存（虽然 256G 不差这点，但这是一个好习惯）
    del all_rows 
    
    unique_edges_count = len(merged_data)
    print(f"      ✅ 聚合完成！压缩后得到 {unique_edges_count:,} 条去重简单边。")
    print(f"      📊 压缩率: {unique_edges_count / (len(merged_data) + 1e-9) * 100:.2f}% (越低说明熟人合作越频繁)")

    # ---------------------------------------------------------
    # 将去重后的字典一次性写回磁盘
    # ---------------------------------------------------------
    print("\n[3/3] 正在将结果落盘...")
    with open(output_file, 'w', encoding='utf-8', newline='') as fout:
        writer = csv.writer(fout)
        writer.writerow(header) # 写入表头
        
        for (u, v), props in tqdm(merged_data.items(), desc="      写入简单图", unit="边", colour="blue"):
            writer.writerow([u, v, json.dumps(props)])
            
    print(f"\n========== 合并彻底完毕！ ==========")
    print(f"请在质量评估代码中，使用新的边表进行评测！")

if __name__ == "__main__":
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
    args = parser.parse_args()

    input_csv = args.input or (args.graph_edges_dir / "authors_authors_e.csv")
    output_csv = args.output or (args.graph_edges_dir / "authors_authors_e_merged.csv")
    merge_author_collaborations(str(input_csv), str(output_csv))
