#!/bin/bash

set -euo pipefail

# 配置
database_path=/duckdb_data/openalex_middle.db

# 建表和导数据

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)" # 获得脚本所在目录

duckdb $database_path < $script_dir/create_schema.sql

duckdb $database_path < $script_dir/load_data.sql


echo "---all finish---"