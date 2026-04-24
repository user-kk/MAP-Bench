#!/bin/bash
set -euo pipefail

# ------ 配置 ------

# 设置文本生成模式
# 1 = 使用 KenLM 模型生成 (高质量，有统计规律，稍慢)
# 0 = 使用 Faker 随机填充 (低质量，无实际意义，极快)
TEXT_GEN_MODE="${TEXT_GEN_MODE:-1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"


# ------ 路径和环境设置 ------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
DATA_GEN_DIR="$SCRIPT_DIR/data_gen"
SOURCE_DATA_ROOT="${MAP_BENCH_SOURCE_DATA_ROOT:-$SCRIPT_DIR/map-s}"
SOURCE_CSV_DIR="$SOURCE_DATA_ROOT/csv-files"
SOURCE_EDGES_DIR="$SOURCE_DATA_ROOT/graph_edges"
SOURCE_ALL_TOPICS_PATH="$SOURCE_DATA_ROOT/csv-files/topics_all.csv"
COLLECT_OUTPUT_DIR="${MAP_BENCH_COLLECT_OUTPUT_DIR:-$SCRIPT_DIR/collect_output}"
GENERATED_ROOT_DIR="${MAP_BENCH_GENERATED_ROOT_DIR:-$SCRIPT_DIR/generated_output}"
EMBED_MODEL_PATH="${MAP_BENCH_EMBED_MODEL_PATH:-$SCRIPT_DIR/all-MiniLM-L6-v2}"

export MAP_BENCH_SOURCE_DATA_ROOT="$SOURCE_DATA_ROOT"
export MAP_BENCH_COLLECT_OUTPUT_DIR="$COLLECT_OUTPUT_DIR"
export MAP_BENCH_GENERATED_ROOT_DIR="$GENERATED_ROOT_DIR"
export MAP_BENCH_EMBED_MODEL_PATH="$EMBED_MODEL_PATH"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo " ERROR：找不到 Python 解释器: $PYTHON_BIN"
    exit 1
fi

if [ ! -d "$SOURCE_DATA_ROOT" ]; then
    echo " ERROR：找不到基础数据集目录"
    echo " 期望路径: $SOURCE_DATA_ROOT"
    exit 1
fi

# ------ 用户输入SF和MODE ------

# 预处理原始数据集 -- 统计信息
if [ "${1:-}" == "--recompute" ]; then
    echo "=== 正在执行【原始】预计算 (读取: map-s) ==="
    mkdir -p "$COLLECT_OUTPUT_DIR"
    echo " 正在删除旧的统计文件..."
    rm -rf "$COLLECT_OUTPUT_DIR"/*
    
    "$PYTHON_BIN" "$DATA_GEN_DIR/precompute_statistics.py" \
        "$SOURCE_CSV_DIR" \
        "$SOURCE_EDGES_DIR" \
        "$SOURCE_ALL_TOPICS_PATH" \
        "$COLLECT_OUTPUT_DIR"
    
    echo "    ... 原始预计算完成。 预处理结果已保存到 $COLLECT_OUTPUT_DIR"
    exit 0
fi

# 执行数据生成
if [ "$#" -ne 2 ]; then
    echo "ERROR：缺少参数。"
    echo " 用法: ./main.sh <SF> <Mode>"
    echo " (1) :数据生成前需要对原始数据集进行预处理：./main.sh --recompute"
    echo " (2) 运行数据生成: ./main.sh 10 1"
    echo " Mode： 1==时间扩展模式 2==密度扩展模式"
    exit 1
fi

SF_ARG=$1
MODE_ARG=$2

echo "=== 正在执行数据生成 ==="
echo " Text Gen Mode = $TEXT_GEN_MODE"
echo " Python 解释器 = $PYTHON_BIN"

echo " Scale Factor = $SF_ARG"
echo " Mode = $MODE_ARG (1==时间扩展, 2==密度扩展)"
echo

# 创建根目录 (如果不存在)
mkdir -p "$GENERATED_ROOT_DIR"

# 为本次运行创建子目录
# 例如: ./generated_output/sf_10_mode_1
OUTPUT_PATH="$GENERATED_ROOT_DIR/sf_${SF_ARG}_mode_${MODE_ARG}"
echo " 生成数据将保存到: $OUTPUT_PATH"

TMP_PATH="$GENERATED_ROOT_DIR/tmp_sf_${SF_ARG}_mode_${MODE_ARG}"

if [ -d "$OUTPUT_PATH" ]; then
    echo " 正在清理旧的输出目录: $OUTPUT_PATH"
    rm -rf "$OUTPUT_PATH"
fi
mkdir -p "$OUTPUT_PATH"
# 创建所有子目录
echo " 正在创建目录结构..."
mkdir -p "$OUTPUT_PATH/csv-files"
mkdir -p "$OUTPUT_PATH/document"
mkdir -p "$OUTPUT_PATH/vector"
mkdir -p "$OUTPUT_PATH/graph_vertices"
mkdir -p "$OUTPUT_PATH/graph_edges"


echo " 正在复制 'map-s' 数据..."

# csv-files
cp "$SOURCE_DATA_ROOT/csv-files/authors.csv" "$OUTPUT_PATH/csv-files/authors.csv"
cp "$SOURCE_DATA_ROOT/csv-files/works.csv" "$OUTPUT_PATH/csv-files/works.csv"
cp "$SOURCE_DATA_ROOT/csv-files/topics.csv" "$OUTPUT_PATH/csv-files/topics.csv"
cp "$SOURCE_DATA_ROOT/csv-files/institutions.csv" "$OUTPUT_PATH/csv-files/institutions.csv" 2>/dev/null || true
cp "$SOURCE_DATA_ROOT/csv-files/institutions_geo.csv" "$OUTPUT_PATH/csv-files/institutions_geo.csv" 2>/dev/null || true


# document
cp "$SOURCE_DATA_ROOT/document/authors_doc.csv" "$OUTPUT_PATH/document/authors_doc.csv"
cp "$SOURCE_DATA_ROOT/document/works_doc.csv" "$OUTPUT_PATH/document/works_doc.csv"

# vector 
cp "$SOURCE_DATA_ROOT/vector/works_vec.csv" "$OUTPUT_PATH/vector/works_vec.csv" 2>/dev/null || true
cp "$SOURCE_DATA_ROOT/vector/topics_vec.csv" "$OUTPUT_PATH/vector/topics_vec.csv" 2>/dev/null || true

# graph_vertices
cp "$SOURCE_DATA_ROOT/graph_vertices/authors_v.csv" "$OUTPUT_PATH/graph_vertices/authors_v.csv"
cp "$SOURCE_DATA_ROOT/graph_vertices/works_v.csv" "$OUTPUT_PATH/graph_vertices/works_v.csv"
cp "$SOURCE_DATA_ROOT/graph_vertices/topics_v.csv" "$OUTPUT_PATH/graph_vertices/topics_v.csv"

# graph_edges
cp "$SOURCE_DATA_ROOT/graph_edges/works_authors_e.csv" "$OUTPUT_PATH/graph_edges/works_authors_e.csv"
cp "$SOURCE_DATA_ROOT/graph_edges/works_topics_e.csv" "$OUTPUT_PATH/graph_edges/works_topics_e.csv"
cp "$SOURCE_DATA_ROOT/graph_edges/works_referenced_works_e.csv" "$OUTPUT_PATH/graph_edges/works_referenced_works_e.csv"
cp "$SOURCE_DATA_ROOT/graph_edges/authors_authors_e.csv" "$OUTPUT_PATH/graph_edges/authors_authors_e.csv"

echo " 基础数据复制并重命名完毕。"

if [ -d "$TMP_PATH" ]; then
    echo " 正在清理旧的临时目录: $TMP_PATH"
    rm -rf "$TMP_PATH"
fi
echo " 正在创建临时目录结构..."
mkdir -p "$TMP_PATH/csv-files"
mkdir -p "$TMP_PATH/document"
mkdir -p "$TMP_PATH/vector"
mkdir -p "$TMP_PATH/graph_vertices"
mkdir -p "$TMP_PATH/graph_edges"
# 传递参数并执行主生成脚本
"$PYTHON_BIN" "$DATA_GEN_DIR/main_generator.py" "$SF_ARG" "$MODE_ARG" "$OUTPUT_PATH" "$TMP_PATH" "$TEXT_GEN_MODE"

echo
echo " 生成器运行完毕。"
echo
