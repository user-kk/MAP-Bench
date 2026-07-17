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
- `script/polystore/`: loading, query, and container helper scripts for the Polyglot implementation.

Each system directory typically contains two subdirectories:

- `load/`: create schema/collections, load data, create indexes, and collect storage size statistics.
- `query/`: run end-to-end latency benchmarks, resource profiling, query complexity analysis, and execution plan collection.

## Data Source and Data Generation

### Datasets

The pre-built MAP-Bench datasets (MAP-S / MAP-M / MAP-L) are available for download from Baidu Netdisk:

- https://pan.baidu.com/s/1ypordpefzTG0HzhcwyFXiQ?pwd=sd6b (password: `sd6b`)

Alternatively, you can download raw OpenAlex snapshots and generate the datasets yourself using the scripts in [openalex-automated-pipeline](https://anonymous.4open.science/r/openalex-automated-pipeline-C372/).

### Data Generator

For details about the data generator, see: [English README](generator/README.md) / [中文说明](generator/README_zh.md)

> **Recommended usage.** For MAP-Bench, we recommend using the **real datasets** (MAP-S / MAP-M / MAP-L) for primary performance evaluation, as they preserve cross-model semantic consistency and real-world data characteristics.
> 
> The **Data Generator** is mainly intended for:
> 
> - Filling scale gaps when ETL-derived real datasets are only available at discrete sizes and you need an intermediate / fine-grained scale. In this case, the generator extends the seed dataset guided by statistics learned from real data.
> - Stress testing / robustness analysis when you want to produce controlled non-realistic extreme distributions for targeted what-if experiments.
> 
> The generator is not meant to replace large-scale real datasets obtained directly via ETL from OpenAlex snapshots. If you need larger real datasets, we recommend running the same ETL pipeline on the OpenAlex snapshot to extract them.


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

### GredoDB

Repository URL: https://github.com/whu-totemdb/GredoDB

Download URL: https://gredodb-1382773346.cos.ap-singapore.myqcloud.com/GredoDB.zip

Update the data path in `load_data.sql` and the configuration in `main.sh`, and run `main.sh`. This process may also take a long time, so it is recommended to reserve sufficient running time.

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

### Polyglot system: relational `PostgreSQL 14.20`, document `MongoDB 6.0.26`, graph `Neo4j 5.24.2`, vector `Milvus 2.3.4`

Run the following command in the `util` directory to start the Polyglot cluster with Docker:

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

### GredoDB

Modify `DB_CONF` in `bench_gredodb.py` and run the script as indicated by the comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/gredodb/query/README.md](script/gredodb/query/README.md)

### AgensGraph 2.16.0 + pgvector 0.6.2

Modify `DB_CONF` in `bench_agensgraph.py` and run the script as indicated by the comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/agensgraph/query/README.md](script/agensgraph/query/README.md)

### DuckDB 1.2.2

Modify `DB_CONF` in `bench_duckdb.py` and run the script as indicated by the comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/duckdb/query/README.md](script/duckdb/query/README.md)

### Polyglot system

Modify `DB_CONF` in `bench_poly.py` and run the script as indicated by the comments. The script updates the median time and the latency of each run in the CSV file in real time.

See also: [script/polystore/query/README.md](script/polystore/query/README.md)

## Workload Suite (Queries)

MAP-Bench includes **19 read-only analytical queries** organized as **multi-stage, cross-model pipelines**. Each query is labeled by an execution pattern:

- **H (Hybrid-Lookup)**: highly selective, interactive lookups across models
- **A (Attribute-Aggregation)**: scan / unnest / group-by / rank heavy analytics
- **V (Vector-Similarity)**: semantic retrieval (ANN / distance ranking) inside cross-model pipelines
- **G (Graph-Traversal)**: multi-hop traversal / shortest-path / pattern matching with cross-model filtering


### Query Catalog

The table below summarizes the workload queries. “Models” are listed in the order of first appearance across query stages.

| Query | Description | Models |
|------:|-------------|:------:|
| H1 | Find authors by name variants and list their publications | D-G-R |
| H2 | Find co-authors of a given author with their affiliations | G-R |
| H3 | Find papers belonging to a given topic, ranked by structural and semantic relevance | R-G-V |
| H4 | Find references of a paper with authors | G-D |
| H5 | Find intermediate papers on the citation path between two works, ranked by topic relevance | G-D-V |
| A1 | Analyze top publishing institutions and their primary research fields | R-D-G |
| A2 | Analyze collaboration frequency for a given author, grouped by year | G-D-R |
| A3 | Analyze topic distribution for researchers at a given institution | R-G |
| A4 | Analyze which institutions lead in the most active research topic | R-D-G |
| A5 | Analyze prolific authors in a given topic whose papers contain specific keywords | R-D |
| A6 | Analyze top papers across related research areas | V-G-R |
| V1 | Recommend papers similar to a highly-cited seed paper within its citation network | R-D-G-V |
| V2 | Recommend novel papers beyond a paper’s existing references | G-V |
| V3 | Recommend semantically similar papers, filtered by keywords and time range | V-R-D |
| V4 | Recommend papers similar to a given paper in a specified topic, with bibliographic details | R-D-V |
| G1 | Explore potential collaborators in a specific research field | R-G-D-V |
| G2 | Explore the influence of papers along the shortest citation path between two works | G-R-D |
| G3 | Explore the citation neighborhood of a paper with author details | G-R-D |
| G4 | Explore interdisciplinary papers bridging two research fields | R-G-D |


### Operator Coverage (by Query)

The following table summarizes the **main operators** exercised by each query (in stage order) and the **data models** involved.
Note that this is a **high-level** characterization; exact physical operators and implementations may vary across systems.

<details open>
<summary><b>Model coverage & key operators per query</b></summary>

<br/>

| Query | Key Operators (in Stage Order) | R | D | G | V |
|:-----:|--------------------------------|:-:|:-:|:-:|:-:|
| H1 | Document containment predicate → graph pattern matching → group-by aggregation | ✓ | ✓ | ✓ |  |
| H2 | Graph pattern matching → relational join | ✓ |  | ✓ |  |
| H3 | Relational join → graph pattern matching → vector distance computation | ✓ |  | ✓ | ✓ |
| H4 | Graph pattern matching → document join → nested document extraction |  | ✓ | ✓ |  |
| H5 | Shortest-path search → nested document path access → vector distance computation |  | ✓ | ✓ | ✓ |
| A1 | Nested document unnesting → group-by aggregation → graph pattern matching → window aggregation | ✓ | ✓ | ✓ |  |
| A2 | Graph pattern matching → nested document unnesting → group-by aggregation → window aggregation → nested document construction | ✓ | ✓ | ✓ |  |
| A3 | Relational join → graph pattern matching → group-by aggregation | ✓ |  | ✓ |  |
| A4 | Nested document unnesting → group-by aggregation → graph pattern matching → group-by aggregation | ✓ | ✓ | ✓ |  |
| A5 | Document field-existence predicate → nested document unnesting → group-by aggregation → relational join/filter | ✓ | ✓ |  |  |
| A6 | Vector ANN search → graph pattern matching → window aggregation | ✓ |  | ✓ | ✓ |
| V1 | Relational-document filtering → multi-hop graph search → vector ANN search → relational join | ✓ | ✓ | ✓ | ✓ |
| V2 | Graph pattern matching → vector ANN search with exclusion |  |  | ✓ | ✓ |
| V3 | Vector ANN search → relational filtering → document field-existence predicate | ✓ | ✓ |  | ✓ |
| V4 | Relational-document filtering → vector ANN search → nested document construction | ✓ | ✓ |  | ✓ |
| G1 | Relational lookup → multi-hop graph search → document containment predicate → vector distance computation → group-by aggregation | ✓ | ✓ | ✓ | ✓ |
| G2 | Shortest-path search → relational join → nested document unnesting → group-by aggregation | ✓ | ✓ | ✓ |  |
| G3 | Multi-hop graph search → relational join → nested document path access | ✓ | ✓ | ✓ |  |
| G4 | Relational filtering → graph pattern matching → relational join → nested document path access | ✓ | ✓ | ✓ |  |

</details>

### Application-oriented View

While MAP-Bench is primarily organized by execution patterns (H/A/V/G), the table below provides an **application-oriented** categorization for readers who prefer to understand the workloads by scenario semantics.

<details open>
<summary><b>Application-oriented categorization of MAP-Bench queries</b></summary>

<br/>

| Application Scenario | Description | Queries |
|---|---|---|
| Similar-paper retrieval and recommendation | Retrieve papers semantically related to a given paper or topic for recommendation and literature exploration. | H3, H5, V1, V2, V3, V4 |
| Author lookup and collaboration analysis | Identify co-authors or potential collaborators and characterize collaboration dynamics. | H1, H2, A2, G1 |
| Impact and trend analysis | Measure the influence of institutions, authors, or topics and analyze research trends. | A1, A3, A4, A5, A6 |
| Citation and structural path exploration | Explore citation neighborhoods and knowledge propagation along shortest paths. | H4, G2, G3, G4 |

</details>
