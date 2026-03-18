#!/bin/bash
set -euo pipefail

# 日志目录（不存在就自动建）
LOG_DIR="logs"
mkdir -p "$LOG_DIR"
start=$(date +%s)

python load_data.py -c > "$LOG_DIR/all.log" 2>&1

# 1. 同时后台跑 4 条命令，输出各自进日志
python load_data.py -p > "$LOG_DIR/p.log" 2>&1 &   # -p 的日志
python load_data.py -m > "$LOG_DIR/m.log" 2>&1 &   # -m 的日志
python load_data.py -n > "$LOG_DIR/n.log" 2>&1 &   # -n 的日志
python load_data.py -v > "$LOG_DIR/v.log" 2>&1 &   # -v 的日志

# 2. 等待全部结束
wait
end=$(date +%s)
elapsed=$((end - start))
echo "四条命令全部完成，耗时 ${elapsed} 秒"