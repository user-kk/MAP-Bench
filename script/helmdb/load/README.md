[English](README.md) | [中文](README_zh.md)

## Loading Guide

- This directory contains the scripts for schema creation, data import, index creation, graph loading, and storage-size statistics for HelmDB.

## Files

- `main.sh`: main loading entry.
- `create_schema.sql`: creates the base schema.
- `load_data.sql`: imports relational, document, and vector-related data.
- `create_index.sql`: creates the indexes required by the benchmark queries.
- `load_graph.sql`: imports graph-related structures.
- `get_size.py`: collects per-model storage statistics.

## Configuration to Update

Before running `main.sh`, update:

- `port`
- `database`

You also need to update the raw data path inside `load_data.sql`.

## Prerequisites

- Use the latest `helmdb-develop` branch
- Compile the `ldbc` plugin in advance

## Workflow

`main.sh` performs the following steps:

1. Run `create_schema.sql` with `gsql`.
2. Run `load_data.sql` with `gsql`.
3. Run `create_index.sql` with `gsql`.
4. Run `load_graph.sql` with `gsql`.

## Run

```bash
bash main.sh
```

## Notes

- HelmDB query scripts use Python 3.6.8 because of client-side limitations, while the loading workflow itself mainly depends on `gsql`.
- For multi-dataset imports, update `database` and the paths inside `load_data.sql` for each dataset.
