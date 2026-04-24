[English](README.md) | [中文](README_zh.md)

## Loading Guide

- This directory contains the scripts for schema creation, data import, index creation, and storage-size statistics for AgensGraph.

## Files

- `main.sh`: main loading entry.
- `create_schema.sql`: creates the schema, labels, and edge structures.
- `load_data.sql`: imports relational, document, graph, and vector-related data.
- `create_index.sql`: creates the indexes required by the benchmark queries.
- `get_size.py`: collects per-model storage statistics.

## Configuration to Update

Before running `main.sh`, update the following values according to your environment:

- `port`
- `user`
- `database`
- `psql_path`

You also need to update the raw data path inside `load_data.sql`.

## Prerequisites

- Install `pgvector`
- Install `file_fdw`

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

- Both loading and index creation can take a long time.
- For multi-dataset imports, update `database` and the paths inside `load_data.sql` accordingly.
