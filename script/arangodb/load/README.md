[English](README.md) | [中文](README_zh.md)

## Loading Guide

- This directory contains the scripts for schema creation, data import, index creation, and storage-size statistics for ArangoDB.

## Files

- `main.sh`: main loading entry.
- `create_schema.js`: creates collections, graphs, and vector-related objects.
- `create_index.js`: creates the indexes required by the benchmark queries.
- `get_size.py`: collects per-model storage statistics.
- `preproc/`: preprocesses raw CSV files into JSONL files suitable for `arangoimport`.

## Configuration to Update

Before running `main.sh`, update the following fields according to your environment:

- `username`
- `password`
- `database`
- `thread_num`
- `force_rebuild`
- `build_dir`
- `data_dir`

Here:
- `build_dir` stores intermediate JSONL files generated during preprocessing.
- `data_dir` should point to the root directory of the dataset you want to import.

## Workflow

`main.sh` performs the following steps:

1. Check whether `arangosh`, `arangoimport`, and `python3` are available.
2. Run the scripts in `preproc/` to convert document, graph, and vector CSV files into JSONL.
3. Execute `create_schema.js` to create collections and graph structures.
4. Import relational, document, graph, and vector data via `arangoimport`.
5. Execute `create_index.js` to build indexes.

## Run

```bash
bash main.sh
```

## Notes

- Large datasets may take a long time to import.
- If index creation times out, rerun the index step separately.
- For multi-dataset imports, adjust `database`, `build_dir`, and `data_dir` for each dataset.
