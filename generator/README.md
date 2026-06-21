# MAP-Bench Data Generator
[English](README.md) | [中文](README_zh.md)

## Overview

This directory contains the MAP-Bench data generator based on an OpenAlex subset.

The current generator contains three code parts:

- `data_gen/`: the main data generation pipeline.
- `TRIGRAM_TRAIN/`: unstructured text generation model training scripts.
- `quality_eval/`: evaluation of the distribution of generated data


## Generation Modes

Two generation modes are provided with a configurable scale factor SF.

- Mode 1: temporal expansion mode. It extends the timeline of the original dataset and simulates the emergence of new authors and new topics while generating new works.
- Mode 2: density expansion mode. It keeps the original time span unchanged and increases the number of works under the same topic and author constraints.

The following main directories are involved during execution:

- `collect_output/`: stores the precomputed statistics of the base dataset.
- `generated_output/`: stores generated results. Each run creates a parameter-specific subdirectory here.

## Default Directory Layout

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

Where:

- `map-s/`: the base dataset used for generation.
- `map-l/`: the dataset used to train the trigram model.
- The dataset directories must follow the layout above. Data source: <https://pan.baidu.com/s/1Jc7W_h4a-6iTLi2EnUUuOw?pwd=gerd>
- `all-MiniLM-L6-v2/`: the vector word embedding model, downloaded from <https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>
- `corpus/`: the training corpus extracted from `map-l`.
- `models/`: the trained KenLM model directory.
- `vocab.txt`: the global vocabulary file used during generation.

## Not Included in the Repository

The following contents are not included in this repository

- datasets such as `map-s` and `map-l`
- the vector word embedding model `all-MiniLM-L6-v2`
- the corpora, vocabulary files, and KenLM model artifacts generated under `TRIGRAM_TRAIN/`

Users need to train or download these assets separately

## Environment Variables

The following environment variables can override the default paths:

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

The following variables control generation throughput:

- `MAP_BENCH_PROCESS_NUM`: number of worker processes.
- `MAP_BENCH_TASK_BATCH_SIZE`: task batch size submitted to workers.
- `MAP_BENCH_PRELOAD_KENLM_TOP_N`: number of KenLM models preloaded by each worker.
- `MAP_BENCH_P2_CACHE`: enable the top-k candidate cache.
- `MAP_BENCH_P2_CACHE_SIZE`: maximum top-k cache entries per worker.
- `MAP_BENCH_P4_SCORE_CACHE`: enable the KenLM word-score cache.
- `MAP_BENCH_P4_SCORE_CACHE_SIZE`: maximum score-cache entries per worker.
- `MAP_BENCH_CACHE_STATS`: print cache statistics when enabled.

## Usage

### 1. Precompute statistics for the base dataset

```bash
cd generator
./main.sh --recompute
```

### 2. Generate data

```bash
cd generator
./main.sh sf mode
```

Example:

- `./main.sh 1.5 2`

High-throughput example:

```bash
cd generator
./main.sh --recompute
taskset -c 0-71 env \
  MAP_BENCH_PROCESS_NUM=72 \
  MAP_BENCH_TASK_BATCH_SIZE=1 \
  MAP_BENCH_PRELOAD_KENLM_TOP_N=0 \
  MAP_BENCH_P2_CACHE=1 \
  MAP_BENCH_P2_CACHE_SIZE=200000 \
  MAP_BENCH_P4_SCORE_CACHE=1 \
  MAP_BENCH_P4_SCORE_CACHE_SIZE=64 \
  ./main.sh 1.05 1
```

Adjust the CPU range and worker count to the local machine.

## TRIGRAM_TRAIN

The trigram model is used to generate unstructured text. Before running the generator, execute:

```bash
cd generator/TRIGRAM_TRAIN
python3 01_extract_corpus.py
python3 create_global_vocab.py
python3 02_train_models.py
```

## Tested Environment

Python 3.12.3
Faker==37.12.0
numpy==2.3.4
pandas==2.3.3
tqdm==4.67.1
