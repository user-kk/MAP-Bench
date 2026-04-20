# MAP-Bench 数据生成器
[English](README_en.md) | [中文](README.md)

## 介绍

该目录包含基于 OpenAlex 子集的 MAP-Bench 数据生成器。

当前生成器包含两部分代码：

- `data_gen/`：主数据生成流程。
- `TRIGRAM_TRAIN/`：非结构化文本生成模型训练脚本。


## 生成模式

提供两种生成模式 Mode 和自定义比例因子 SF。

- 模式一：时间扩展模式。在原始数据集的时间节点基础上向后扩展，在生成文章数据的同时模拟新作者和新主题的生成。
- 模式二：密度扩展模式。维持原始数据集的时间跨度不变，仅在同主题和作者约束下增加文章数量。

运行过程中涉及的主要目录如下：

- `collect_output/`：存储基础数据集的预计算统计信息。
- `generated_output/`：存储生成结果。每次执行生成都会在该目录下创建对应参数的子目录。

## 默认目录结构

```text
generator/
├── data_gen/
├── TRIGRAM_TRAIN/
│   ├── corpus/
│   ├── models/
│   └── vocab.txt
├── map-s/
│   ├── csv-files/
│   ├── document/
│   ├── graph_edges/
│   ├── graph_vertices/
│   └── vector/
├── map-l/
│   ├── csv-files/
│   ├── document/
│   ├── graph_edges/
│   ├── graph_vertices/
│   └── vector/
├── all-MiniLM-L6-v2/
├── collect_output/
└── generated_output/
```

其中：

- `map-s/`：用于生成的基础数据集。
- `map-l/`：用于训练 trigram 模型的数据集。
- 数据集目录必须按照上述结构对齐，数据来源：<https://github.com/thriaaaa/openalex-automated-pipeline>
- `all-MiniLM-L6-v2/`：向量词嵌入模型下载自<https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>
- `corpus/`：从 `map-l` 中提取得到的训练语料目录。
- `models/`：训练完成后的 KenLM 模型目录。
- `vocab.txt`：生成时使用的全局词表文件。

## 仓库中不包含的内容

以下内容不会包含在本仓库中仓

- 数据集，例如 `map-s`、`map-l`
- 向量词嵌入模型 `all-MiniLM-L6-v2`
- `TRIGRAM_TRAIN/` 下训练生成的语料、词表和 KenLM 模型产物

这些内容需要用户自行训练或下载

## 环境变量

可以通过以下环境变量覆盖默认路径：

- `MAP_BENCH_SOURCE_DATA_ROOT`
- `MAP_BENCH_COLLECT_OUTPUT_DIR`
- `MAP_BENCH_GENERATED_ROOT_DIR`
- `MAP_BENCH_EMBED_MODEL_PATH`
- `MAP_BENCH_NGRAM_DIR`
- `MAP_BENCH_NGRAM_MODEL_DIR`
- `MAP_BENCH_NGRAM_VOCAB_PATH`
- `MAP_BENCH_TRIGRAM_SOURCE_DATA_ROOT`
- `MAP_BENCH_LMPLZ_PATH`
- `MAP_BENCH_BUILD_BINARY_PATH`
- `PYTHON_BIN`

## 使用说明

### 1. 预计算基础数据集统计信息

```bash
cd generator
./main.sh --recompute
```

### 2. 生成数据

```bash
cd generator
./main.sh sf mode
```

示例：

- `./main.sh 1.5 2`

## TRIGRAM_TRAIN 使用方式

trigram模型用于生成非结构化文本，在执行生成器前需执行：

```bash
cd generator/TRIGRAM_TRAIN
python3 01_extract_corpus.py
python3 create_global_vocab.py
python3 02_train_models.py
```

## 测试环境

Python 3.12.3  
Faker==37.12.0  
numpy==2.3.4  
pandas==2.3.3  
tqdm==4.67.1  
