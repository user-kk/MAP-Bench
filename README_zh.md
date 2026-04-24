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
- `script/polystore/`：Polystore 的导入、查询与容器辅助脚本。

各系统目录通常包含两个子目录：

- `load/`：负责建表/建集合、导入数据、创建索引以及统计存储大小。
- `query/`：负责端到端延迟、资源占用、查询复杂度与执行计划等测试。


## 数据来源与数据生成

### 原始数据来源

本 benchmark 使用的原始数据来源仓库如下：

- 原始数据来源仓库：https://github.com/thriaaaa/openalex-automated-pipeline

### 数据生成器

数据生成器相关内容详见：[English README](generator/README.md) / [中文说明](generator/README_zh.md)

仓库中不包含数据生成器依赖的基础数据集、向量模型以及训练后的 trigram 模型。

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

源码地址：https://github.com/whu-totemdb/GredoDB

下载包地址：https://gredodb-1382773346.cos.ap-singapore.myqcloud.com/Gredo.zip

需要先编译好 `ldbc` 插件，并修改 `load_data.sql` 中的数据路径以及 `main.sh` 中的配置信息，然后执行 `main.sh`。该过程同样可能持续较长时间，建议预留充足运行时间。

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

### Polystore 系统：关系 `PostgreSQL 14.20`，文档 `MongoDB 6.0.26`，图 `Neo4j 5.24.2`，向量 `Milvus 2.3.4`

在 `util/` 目录下执行如下命令，可使用 Docker 启动 Polystore 集群：

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

源码地址：https://github.com/whu-totemdb/GredoDB

下载包地址：https://gredodb-1382773346.cos.ap-singapore.myqcloud.com/Gredo.zip

修改 `bench_gredodb.py` 中的 `DB_CONF` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/gredodb/query/README.md](script/gredodb/query/README.md)

### AgensGraph 2.16.0 + pgvector 0.6.2

修改 `bench_agensgraph.py` 中的 `DB_CONF` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/agensgraph/query/README.md](script/agensgraph/query/README.md)

### DuckDB 1.2.2

修改 `bench_duckdb.py` 中的 `DB_CONF` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/duckdb/query/README.md](script/duckdb/query/README.md)

### Polystore 系统

修改 `bench_poly.py` 中的 `DB_CONF` 配置信息后，按脚本内注释执行即可。脚本会实时将每次运行时间以及当前中位数写入 CSV 文件。

更详细说明见：[script/polystore/query/README.md](script/polystore/query/README.md)
