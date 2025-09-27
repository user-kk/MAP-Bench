#!/bin/bash

set -euo pipefail


export PGPASSWORD='linux123'

# 配置
port=5555
user=agensgraph
database=openalex_mini
psql_path=/usr/local/agensgraph/bin/psql



script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)" # 获得脚本所在目录
 
$psql_path -U $user -d $database -p $port -f $script_dir/create_schema.sql
echo "建表完成"

$psql_path -U $user -d $database -p $port -f $script_dir/load_data.sql
echo "导入数据完成"


echo "---all finish---"
