[English](README.md) | [中文](README_zh.md)

## Loading Guide

- This directory contains the scripts for schema creation, data import, index creation, and storage-size statistics for DuckDB.

## Files

- `main.sh`: main loading entry.
- `create_schema.sql`: creates relational and graph/vector-related objects.
- `load_data.sql`: imports the raw data.
- `create_index.sql`: creates the indexes required by the benchmark queries.
- `get_size.py`: collects per-model storage statistics.

## Configuration to Update

Before running `main.sh`, update:

- `database_path`

You also need to update the raw data path inside `load_data.sql`.

## Workflow

`main.sh` performs the following steps:

1. Execute `create_schema.sql`.
2. Execute `load_data.sql`.
3. Execute `create_index.sql`.

## Run

```bash
bash main.sh
```

## Notes

- This benchmark currently depends on DuckDB 1.2.2.
- On older systems, you may also need to handle glibc compatibility yourself.
- For multi-dataset imports, update `database_path` and the paths inside `load_data.sql` for each dataset.
