#!/bin/bash

set -euo pipefail

# 配置
port=9999
database=openalex_middle 



script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)" # 获得脚本所在目录
 
gsql -d $database -p $port -r -f $script_dir/create_schema.sql
echo "建表完成"

gsql -d $database -p $port -r -f $script_dir/load_data.sql
echo "导入数据完成"

gsql -d $database -p $port -r -f $script_dir/load_graph.sql
echo "创建图缓存完成"


echo "---all finish---"
