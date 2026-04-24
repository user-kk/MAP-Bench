[English](README.md) | [中文](README_zh.md)

## Loading Guide

- This directory contains the loading scripts and storage-size statistics scripts for the Polystore system.

## Files

- `main.sh`: main loading entry.
- `load_data.py`: imports data into PostgreSQL, MongoDB, Neo4j, and Milvus.
- `get_size.py`: collects per-model storage statistics for the Polystore system.

## Configuration to Update

`load_data.py` still works in a single-dataset style. Before running it, update the following constants according to your deployment:

- `DB_NAME`
- `DATA_ROOT`
- `CONTAINER_DATA_ROOT`
- `TMP_ROOT`
- `CONTAINER_TMP_ROOT`

If your container ports or credentials differ from the defaults, also review the connection-related constants at the top of the file.

## Workflow

`main.sh` performs the following steps:

1. Run `python load_data.py -c` to create the target dataset inside the Polystore system.
2. Then run the following in parallel:
   - `python load_data.py -p` for PostgreSQL
   - `python load_data.py -m` for MongoDB
   - `python load_data.py -n` for Neo4j
   - `python load_data.py -v` for Milvus

## Run

```bash
bash main.sh
```

If you want to load only one backend, you can also run the subcommands directly:

```bash
python load_data.py -p
python load_data.py -m
python load_data.py -n
python load_data.py -v
```

## Prerequisites

- Start the corresponding Polystore container stack in `util/` first.
- Install dependencies such as `pymongo`, `psycopg`, `neo4j`, `pymilvus`, and `pandas`.

## Notes

- If you use multi-dataset container stacks, switch to the target dataset before running the loader.
- Unlike the query scripts, `load_data.py` does not yet provide unified `-d` dataset switching, so the dataset-related constants still need to be edited manually.
