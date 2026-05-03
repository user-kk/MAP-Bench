# MAP-Bench
[English](README.md) | [中文](README_zh.md)

<div align="center">
    <img src="logo.svg" width="300" alt="Logo" />
</div>

## 介绍

本仓库收录了 MAP-Bench 的复现实验脚本，主要包括数据导入脚本、查询评测脚本和数据生成器。

MAP-Bench：Multi-model Analytical Processing Benchmark。

也可以理解成 Multi-model Analytics Pipeline，因为负载是通过不同子查询的查询分析流水线组织起来的。

Map（地图/映射）暗示了连接和导航。Benchmark 的核心是将不同模型连接起来，像地图一样展示多模数据之间的关联。

## 目录概览

仓库根目录当前或计划包含以下主要内容：

- `script/`：各系统的导入、查询、统计与辅助脚本。
- `generator/`：数据生成器，用于对数据集进行扩展

`script/` 下的主要子目录如下：

- `script/common/`：各系统共享的通用脚本、统计脚本、绘图脚本以及多数据集参数配置文件。
- `script/arangodb/`：ArangoDB 的导入脚本与查询脚本。
- `script/agensgraph/`：AgensGraph 的导入脚本与查询脚本。
- `script/duckdb/`：DuckDB 的导入脚本与查询脚本。
- `script/gredodb/`：GredoDB 的导入脚本与查询脚本。
- `script/polystore/`：Polyglot 的导入、查询与容器辅助脚本。

各系统目录通常包含两个子目录：

- `load/`：负责建表/建集合、导入数据、创建索引以及统计存储大小。
- `query/`：负责端到端延迟、资源占用、查询复杂度与执行计划等测试。


## 数据来源与数据生成

### 数据集

预先构建好的 MAP-Bench 数据集（MAP-S / MAP-M / MAP-L）可从百度网盘下载获取：

- https://pan.baidu.com/s/1Jc7W_h4a-6iTLi2EnUUuOw?pwd=gerd (提取码：`gerd` )

另外，也可以下载原始的 OpenAlex 快照，并使用 [openalex-automated-pipeline](https://github.com/thriaaaa/openalex-automated-pipeline) 中的脚本自行生成数据集。

### 数据生成器

数据生成器相关内容详见：[English README](generator/README.md) / [中文说明](generator/README_zh.md)

> **Recommended usage.** MAP-Bench 的主要性能评估建议优先使用 **真实数据集**（MAP-S / MAP-M / MAP-L），以保证跨模型语义一致性与真实世界分布特征。
>
> **Data Generator** 主要用于以下场景：
> 1) 当 ETL 得到的真实数据集规模是离散档位，无法满足你需要的“中间规模/细粒度 scale”时，用生成器在真实数据统计特征的引导下进行扩展；  
> 2) 当你希望进行压力测试或鲁棒性分析，需要构造非真实的极端分布时，用生成器进行受控的分布调整。  
>
> 生成器并不旨在替代从 OpenAlex snapshot 直接 ETL 得到的更大规模真实数据；如果需要更大规模的真实数据，推荐使用同样的 ETL pipeline 从 OpenAlex 获取。

## 环境与依赖

当前脚本的主要 Python 依赖如下：

```bash
pip install psycopg2-binary==2.9.8 python-arango==7.3.1 duckdb==1.2.2 "psycopg[binary]==3.2.11"
```

脚本已在 Python 3.13.0 下进行测试。

需要特别说明的是：由于客户端限制，GredoDB 查询相关脚本使用的 Python 版本是 **3.6.8**。

不同系统可能还存在各自的环境要求、插件依赖或兼容性限制，具体说明见对应系统目录下的 `load/README.md` 与 `query/README.md`。

## 数据导入

各系统的数据导入流程存在一定差异。主 README 保留总览说明，系统特定的详细步骤则放在各自的 `load/README.md` 中。

### ArangoDB 3.12.7

在 `main.sh` 中填写对应的配置信息后执行即可。导入过程可能持续较长时间，建议预留充足运行时间。建索引阶段可能出现超时，如遇该情况，可单独重新执行建索引步骤。

更详细说明见：[script/arangodb/load/README.md](script/arangodb/load/README.md)

### GredoDB

仓库地址：https://github.com/whu-totemdb/GredoDB

下载地址：https://gredodb-1382773346.cos.ap-singapore.myqcloud.com/GredoDB.zip

修改 `load_data.sql` 中的数据路径以及 `main.sh` 中的配置信息，然后执行 `main.sh`。该过程同样可能持续较长时间，建议预留充足运行时间。

更详细说明见：[script/gredodb/load/README.md](script/gredodb/load/README.md)

### AgensGraph 2.16.0 + pgvector 0.6.2

需要先安装 `pgvector` 插件和 `file_fdw` 插件（用于导入数据），并修改 `load_data.sql` 中的数据路径以及 `main.sh` 中的配置信息，然后执行 `main.sh`。该过程可能持续较长时间，建议预留充足运行时间。

更详细说明见：[script/agensgraph/load/README.md](script/agensgraph/load/README.md)

### DuckDB 1.2.2

DuckDB 会自动安装 `json`、`vss`、`duckpgq` 插件。完成 `load_data.sql` 数据路径与 `main.sh` 配置信息修改后，执行 `main.sh` 即可。该过程可能持续较长时间，建议预留充足运行时间。

> `duckpgq` 暂时不能很好支持高版本 DuckDB。目前本 benchmark 已知最高稳定版本为 1.2.2（1.3.2 也可以运行，但存在较多 bug，稳定性较差）。
>
> 在 CentOS 7 环境下使用 DuckDB 时，可能需要自行准备较高版本的 glibc。一个可能的处理方式如下：
> ```bash
> patchelf --set-interpreter /path/to/mylibc_2_31/lib/ld-linux-x86-64.so.2 \
>          --set-rpath /path/to/mylibc_2_31/lib \
>          duckdb
> ```
>
> 也可以自行编译 DuckDB 及其相关插件。
>
> 如果不希望在本地自行编译，仓库中也提供了基于 Dockerfile 的构建方式。

更详细说明见：[script/duckdb/load/README.md](script/duckdb/load/README.md)

### Polyglot 系统：关系 `PostgreSQL 14.20`，文档 `MongoDB 6.0.26`，图 `Neo4j 5.24.2`，向量 `Milvus 2.3.4`

在 `util/` 目录下执行如下命令，可使用 Docker 启动 Polyglot 集群：

```bash
docker compose up -d
```

安装如下 Python 依赖：

```bash
pip install pymongo==4.15.4 psycopg[binary]==3.2.11 neo4j==6.0.3 pymilvus==2.6.3 pandas==2.3.3
```

随后执行：

```bash
python script/polystore/load_data.py
```

更详细说明见：[script/polystore/load/README.md](script/polystore/load/README.md)

## 查询评测

各系统的详细查询说明建议保留在对应的 `query/README.md` 中；主 README 仅保留统一入口与核心注意事项，便于快速定位。

### ArangoDB 3.12.7

修改 `bench_arangodb.py` 中的 `client` 和 `db` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/arangodb/query/README.md](script/arangodb/query/README.md)

### GredoDB

修改 `bench_gredodb.py` 中的 `DB_CONF` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/gredodb/query/README.md](script/gredodb/query/README.md)

### AgensGraph 2.16.0 + pgvector 0.6.2

修改 `bench_agensgraph.py` 中的 `DB_CONF` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/agensgraph/query/README.md](script/agensgraph/query/README.md)

### DuckDB 1.2.2

修改 `bench_duckdb.py` 中的 `DB_CONF` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/duckdb/query/README.md](script/duckdb/query/README.md)

### Polyglot 系统

修改 `bench_poly.py` 中的 `DB_CONF` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/polystore/query/README.md](script/polystore/query/README.md)


## 工作负载套件（查询）

MAP-Bench 包含 **19 条只读分析型查询**，以 **多阶段（multi-stage）、跨模型（cross-model）pipeline** 的形式组织。每条查询按其主导 **execution pattern** 归类为：

- **H (Hybrid-Lookup)**：高选择性、交互式跨模型检索
- **A (Attribute-Aggregation)**：以 scan / unnest / group-by / rank 为主的重聚合分析
- **V (Vector-Similarity)**：将 semantic retrieval（ANN / distance ranking）嵌入跨模型 pipeline
- **G (Graph-Traversal)**：multi-hop traversal / shortest-path / pattern matching，并结合跨模型 filtering

### 数据模型缩写（Data Model Legend）

- **R**：relational
- **D**：document
- **G**：graph
- **V**：vector

### 查询目录（Query Catalog）

下表概述了工作负载查询。“Models” 按查询 pipeline 各 stage 中 **首次出现的顺序**列出。

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

### 算子覆盖（Operator Coverage by Query）

下表总结了每条查询在 pipeline 各 stage 中主要覆盖的 **operators** 以及涉及的 **data models**。  
注意：该表为 **高层抽象**；不同系统的物理算子与具体实现可能存在差异。

<details>
<summary><b>点击展开：Model coverage & key operators per query</b></summary>

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

### 应用视角分类（Application-oriented View）

虽然 MAP-Bench 在论文与主 README 中按 execution patterns（H/A/V/G）组织，但下表提供一个 **application-oriented** 的视角，便于读者按场景语义理解查询用途。

<details>
<summary><b>点击展开：Application-oriented categorization of MAP-Bench queries</b></summary>

<br/>

| Application Scenario | Description | Queries |
|---|---|---|
| Similar-paper retrieval and recommendation | Retrieve papers semantically related to a given paper or topic for recommendation and literature exploration. | H3, H5, V1, V2, V3, V4 |
| Collaboration and author-relationship analysis | Identify co-authors or potential collaborators and characterize collaboration dynamics. | H1, H2, A2, G1 |
| Impact and trend analysis | Measure the influence of institutions, authors, or topics and analyze research trends. | A1, A3, A4, A5, A6 |
| Citation exploration and path analysis | Explore citation neighborhoods and shortest-path-based knowledge propagation. | H4, G2, G3, G4 |

</details>
