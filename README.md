# MAP-Bench
[English](README.md) | [中文](README_zh.md)

<div align="center">
    <img src="logo.svg" width="300" alt="Logo" />
</div>

## Introduction

This repository contains the scripts used by MAP-Bench, including data loading scripts and query benchmark scripts.

MAP-Bench stands for **Multi-model Analytical Processing Benchmark**.

It can also be understood as a **Multi-model Analytics Pipeline**, because each workload is organized as a query-analysis pipeline composed of multiple subqueries.

The word *Map* implies connection and navigation. The core idea of the benchmark is to connect different data models and expose their relationships the way a map exposes paths and links.

## Directory Overview

The repository root currently contains the following key items:

- `script/`: all loading, query, statistics, and helper scripts.

The main subdirectories under `script/` are:

- `script/common/`: shared utilities, statistics scripts, plotting scripts, and multi-dataset benchmark configuration files.
- `script/arangodb/`: loading and query scripts for ArangoDB.
- `script/agensgraph/`: loading and query scripts for AgensGraph.
- `script/duckdb/`: loading and query scripts for DuckDB.
- `script/helmdb/`: loading and query scripts for HelmDB.
- `script/polystore/`: loading, query, and container helper scripts for the Polystore implementation.

Each system directory typically contains two subdirectories:

- `load/`: create schema/collections, load data, create indexes, and collect storage-size statistics.
- `query/`: run end-to-end latency benchmarks, resource profiling, complexity analysis, and execution-plan collection.

See the detailed system-specific documentation here:

- [ArangoDB Load](script/arangodb/load/README.md) / [ArangoDB Query](script/arangodb/query/README.md)
- [AgensGraph Load](script/agensgraph/load/README.md) / [AgensGraph Query](script/agensgraph/query/README.md)
- [DuckDB Load](script/duckdb/load/README.md) / [DuckDB Query](script/duckdb/query/README.md)
- [HelmDB Load](script/helmdb/load/README.md) / [HelmDB Query](script/helmdb/query/README.md)
- [Polystore Load](script/polystore/load/README.md) / [Polystore Query](script/polystore/query/README.md)

## Dependencies

The main Python dependencies are:

```bash
pip install psycopg2-binary==2.9.8 python-arango==7.3.1 duckdb==1.2.2 "psycopg[binary]==3.2.11"
```

The scripts have been tested under Python 3.13.0.

One important exception is HelmDB: due to client-side limitations, the HelmDB query scripts use **Python 3.6.8**.

## Data Loading

### ArangoDB 3.12.7

Fill in the required configuration in `main.sh` and run it. Loading may take a long time, so an overnight run is recommended. Index creation may time out; in that case, rerun the index step separately.

See also: [script/arangodb/load/README.md](script/arangodb/load/README.md)

### HelmDB latest `helmdb-develop` branch [link](https://gitee.com/whudb/HELMDB)

Make sure the ldbc plugin is compiled first, update the data path in `load_data.sql`, adjust the configuration in `main.sh`, then run `main.sh`. This process may also take a long time.

See also: [script/helmdb/load/README.md](script/helmdb/load/README.md)

### AgensGraph 2.16.0 + pgvector 0.6.2

Install the `pgvector` and `file_fdw` extensions first, update the data path in `load_data.sql`, adjust the configuration in `main.sh`, then run `main.sh`.

See also: [script/agensgraph/load/README.md](script/agensgraph/load/README.md)

### DuckDB 1.2.2

DuckDB installs the `json`, `vss`, and `duckpgq` plugins automatically. Update the data path in `load_data.sql`, adjust the configuration in `main.sh`, then run `main.sh`.

> `duckpgq` does not currently support high DuckDB versions well. The highest stable version for this benchmark is 1.2.2 (1.3.2 is also supported but has many bugs and is unstable).
>
> On CentOS 7, DuckDB may require a newer glibc. One possible workaround is:
> ```bash
> patchelf --set-interpreter /path/to/mylibc_2_31/lib/ld-linux-x86-64.so.2 \
         --set-rpath /path/to/mylibc_2_31/lib \
         duckdb
> ```
>
> You can also build DuckDB and its plugins yourself.
>
> If you do not want to compile locally, this repository also provides a Dockerfile-based route.

See also: [script/duckdb/load/README.md](script/duckdb/load/README.md)

### Polystore system: relational `PostgreSQL 14.20`, document `MongoDB 6.0.26`, graph `Neo4j 5.24.2`, vector `Milvus 2.3.4`

Run the following command in the `util/` directory to start the Polystore cluster with Docker:

```bash
docker compose up -d
```

Install the following Python dependencies:

```bash
pip install pymongo==4.15.4 psycopg[binary]==3.2.11 neo4j==6.0.3 pymilvus==2.6.3 pandas==2.3.3
```

Then run:

```bash
python script/polystore/load_data.py
```

See also: [script/polystore/load/README.md](script/polystore/load/README.md)

## Running Queries

Detailed query instructions are now documented under each system's `query/README.md`. The original high-level notes are kept below.

### ArangoDB 3.12.7

Adjust the `client` and `db` configuration in `bench_arangodb.py` and run the script as indicated by the inline comments. The CSV file is updated in real time with per-run latency and running median.

See also: [script/arangodb/query/README.md](script/arangodb/query/README.md)

### HelmDB latest `helmdb-develop` branch [link](https://gitee.com/whudb/HELMDB)

Adjust `DB_CONF` in `bench_helmdb.py` and run the script as indicated by the comments. The CSV file is updated in real time with per-run latency and running median.

See also: [script/helmdb/query/README.md](script/helmdb/query/README.md)

### AgensGraph 2.16.0 + pgvector 0.6.2

Adjust `DB_CONF` in `bench_agensgraph.py` and run the script as indicated by the comments. The CSV file is updated in real time with per-run latency and running median.

See also: [script/agensgraph/query/README.md](script/agensgraph/query/README.md)

### DuckDB 1.2.2

Adjust `DB_CONF` in `bench_duckdb.py` and run the script as indicated by the comments. The CSV file is updated in real time with per-run latency and running median.

See also: [script/duckdb/query/README.md](script/duckdb/query/README.md)

### Polystore system

Adjust `DB_CONF` in `bench_poly.py` and run the script as indicated by the comments. The CSV file is updated in real time with per-run latency and running median.

See also: [script/polystore/query/README.md](script/polystore/query/README.md)
