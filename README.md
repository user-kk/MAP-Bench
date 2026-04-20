# MAP-Bench
[English](README.md) | [中文](README_zh.md)

<div align="center">
    <img src="logo.svg" width="300" alt="Logo" />
</div>

## Introduction

This repository contains the reproduction scripts for MAP-Bench, mainly including data loading scripts, query benchmarking scripts, and the data generator.

MAP-Bench: Multi-model Analytical Processing Benchmark.

It can also be understood as Multi-model Analytics Pipeline, because the workloads are organized as query analysis pipelines composed of different subqueries.

Map implies connection and navigation. The core idea of the benchmark is to connect different models and present the relationships among multimodel data in the same way that a map exposes paths and links.

## Directory Overview

The repository root currently contains or is planned to contain the following key items:

- `script/`: loading, query, statistics, and helper scripts for each system.
- `generator/`: the data generator, used to expand the datasets.

The main subdirectories under `script/` are:

- `script/common/`: shared utilities, statistics scripts, plotting scripts, and multi-dataset benchmark configuration files.
- `script/arangodb/`: loading and query scripts for ArangoDB.
- `script/agensgraph/`: loading and query scripts for AgensGraph.
- `script/duckdb/`: loading and query scripts for DuckDB.
- `script/gredodb/`: loading and query scripts for GredoDB.
- `script/polystore/`: loading, query, and container helper scripts for the Polystore implementation.

Each system directory typically contains two subdirectories:

- `load/`: create schema/collections, load data, create indexes, and collect storage size statistics.
- `query/`: run end-to-end latency benchmarks, resource profiling, query complexity analysis, and execution plan collection.

## Data Source and Data Generation

### Original Data Source

The original data source repository used by this benchmark is:

- Original data source repository: https://github.com/thriaaaa/openalex-automated-pipeline

### Data Generator

For details about the data generator, see: [English README](generator/README.md) / [中文说明](generator/README_zh.md)

The repository does not include the base datasets, the vector model, or the trained trigram model required by the generator.

## Environment and Dependencies

The main Python dependencies are:

```bash
pip install psycopg2-binary==2.9.8 python-arango==7.3.1 duckdb==1.2.2 "psycopg[binary]==3.2.11"
```

The scripts have been tested under Python 3.13.0.

One important exception is GredoDB: due to client-side limitations, the GredoDB query scripts use **Python 3.6.8**.

Different systems may also have their own environment requirements, plugin dependencies, or compatibility constraints. See the corresponding `load/README.md` and `query/README.md` under each system directory for details.

## Data Loading

The data loading workflow differs across systems. The main README keeps a high-level overview, while the detailed system-specific steps are documented in each `load/README.md`.

### ArangoDB 3.12.7

Fill in the required configuration in `main.sh` and run it. The loading process may take a long time, so it is recommended to reserve sufficient running time. Index creation may time out; if that happens, rerun the index creation step separately.

See also: [script/arangodb/load/README.md](script/arangodb/load/README.md)

### GredoDB latest `gredodb-develop` branch [link](https://github.com/whu-totemdb/GredoDB)

Compile the `ldbc` plugin first, then update the data path in `load_data.sql` and the configuration in `main.sh`, and run `main.sh`. This process may also take a long time, so it is recommended to reserve sufficient running time.

See also: [script/gredodb/load/README.md](script/gredodb/load/README.md)

### AgensGraph 2.16.0 + pgvector 0.6.2

Install the `pgvector` and `file_fdw` extensions first, update the data path in `load_data.sql` and the configuration in `main.sh`, and then run `main.sh`. This process may take a long time, so it is recommended to reserve sufficient running time.

See also: [script/agensgraph/load/README.md](script/agensgraph/load/README.md)

### DuckDB 1.2.2

DuckDB automatically installs the `json`, `vss`, and `duckpgq` plugins. After updating the data path in `load_data.sql` and the configuration in `main.sh`, run `main.sh`. This process may take a long time, so it is recommended to reserve sufficient running time.

> `duckpgq` does not currently support high DuckDB versions well. The highest version currently supported by this benchmark is 1.2.2 (1.3.2 is also supported, but it has many bugs and is highly unstable).
>
> On CentOS 7, using DuckDB may require compiling a newer glibc manually, for example:
> ```bash
> patchelf --set-interpreter /path/to/mylibc_2_31/lib/ld-linux-x86-64.so.2 \
>          --set-rpath /path/to/mylibc_2_31/lib \
>          duckdb
> ```
>
> You can also build DuckDB together with its plugins yourself, since the plugins still depend on a newer glibc.
>
> If you do not want to compile it locally, the repository also provides a Dockerfile-based way to build the image.

See also: [script/duckdb/load/README.md](script/duckdb/load/README.md)

### Polystore system: relational `PostgreSQL 14.20`, document `MongoDB 6.0.26`, graph `Neo4j 5.24.2`, vector `Milvus 2.3.4`

Run the following command in the `util` directory to start the Polystore cluster with Docker:

```bash
docker compose up -d
```

Install the following dependencies:

```bash
pip install pymongo==4.15.4 psycopg[binary]==3.2.11 neo4j==6.0.3 pymilvus==2.6.3 pandas==2.3.3
```

Then run:

```bash
python script/polystore/load_data.py
```

See also: [script/polystore/load/README.md](script/polystore/load/README.md)

## Query Benchmarking

The detailed query instructions for each system have been moved to the corresponding `query/README.md`. The high-level overview is kept below.

### ArangoDB 3.12.7

Modify the `client` and `db` configuration in `bench_arangodb.py` and run the script as indicated by the inline comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/arangodb/query/README.md](script/arangodb/query/README.md)

### GredoDB latest `gredodb-develop` branch [link](https://github.com/whu-totemdb/GredoDB)

Modify `DB_CONF` in `bench_gredodb.py` and run the script as indicated by the comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/gredodb/query/README.md](script/gredodb/query/README.md)

### AgensGraph 2.16.0 + pgvector 0.6.2

Modify `DB_CONF` in `bench_agensgraph.py` and run the script as indicated by the comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/agensgraph/query/README.md](script/agensgraph/query/README.md)

### DuckDB 1.2.2

Modify `DB_CONF` in `bench_duckdb.py` and run the script as indicated by the comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/duckdb/query/README.md](script/duckdb/query/README.md)

### Polystore system

Modify `DB_CONF` in `bench_poly.py` and run the script as indicated by the comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/polystore/query/README.md](script/polystore/query/README.md)
