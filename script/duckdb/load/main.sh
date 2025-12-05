#!/bin/bash

set -euo pipefail

# 配置
database_path=/duckdb_data/openalex_middle.db

# 建表和导数据

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)" # 获得脚本所在目录

start=$(date +%s)
duckdb $database_path < $script_dir/create_schema.sql
duckdb $database_path < $script_dir/load_data.sql
echo "导入数据完成，耗时：$(($(date +%s) - start)) 秒"

start=$(date +%s)
duckdb $database_path < $script_dir/create_index.sql
echo "创建索引完成，耗时：$(($(date +%s) - start)) 秒"


echo "---all finish---"