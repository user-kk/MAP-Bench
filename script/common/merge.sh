#!/bin/bash

# 检查参数数量
if [ "$#" -lt 3 ]; then
    echo "用法: $0 <后缀> <目标目录> <输出文件>"
    echo "示例: $0 sql ./sql all_in_one.sql"
    exit 1
fi

# 从命令行参数获取配置
EXTENSION="$1"
DIR="$2"
OUTPUT="$3"

# 检查目标目录是否存在
if [ ! -d "$DIR" ]; then
    echo "错误：目录 '$DIR' 不存在"
    exit 1
fi

# 清空或创建输出文件
> "$OUTPUT"

# 统计处理的文件数量
COUNT=0

# 遍历所有指定后缀的文件，按文件名排序
while IFS= read -r -d '' file; do
    echo "-- ===== File: $(basename "$file") =====" >> "$OUTPUT"
    cat "$file" >> "$OUTPUT"
    echo "" >> "$OUTPUT"  # 加个空行，防止粘连
    ((COUNT++))
done < <(find "$DIR" -type f -name "*.$EXTENSION" -print0 | sort -z)

echo "✅ 合并完成，共处理 $COUNT 个文件，输出：$OUTPUT"