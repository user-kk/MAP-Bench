# MAP-Bench Data Generator
[English](README_en.md) | [中文](README.md)

## Overview

This directory contains the MAP-Bench data generator based on an OpenAlex subset.

The current generator contains two code parts:

- `data_gen/`: the main data generation pipeline.
- `TRIGRAM_TRAIN/`: unstructured text generation model training scripts.


## Generation Modes

Two generation modes are provided with a configurable scale factor SF.

- Mode 1: temporal expansion mode. It extends the timeline of the original dataset and simulates the emergence of new authors and new topics while generating new works.
- Mode 2: density expansion mode. It keeps the original time span unchanged and increases the number of works under the same topic and author constraints.

The main runtime directories are:

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
- The dataset directories must follow the layout above. Data source: <https://github.com/thriaaaa/openalex-automated-pipeline>
- `all-MiniLM-L6-v2/`: sentence embedding model: <https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>
- `corpus/`: the training corpus extracted from `map-l`.
- `models/`: the trained KenLM model directory.
- `vocab.txt`: the global vocabulary file used during generation.

## Not Included in the Repository

The following contents are not included in this repository:

- datasets such as `map-s` and `map-l`
- the sentence embedding model `all-MiniLM-L6-v2`
- the corpora, vocabulary files, and KenLM model artifacts generated under `TRIGRAM_TRAIN/`

Users need to train or download these assets separately.

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
