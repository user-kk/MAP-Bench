# MAP-Bench
[English](README.md) | [中文](README_zh.md)

<div align="center">
    <img src="logo.svg" width="300" alt="Logo" />
</div>

## 介绍

这是 MAP-Bench 的脚本仓库，包括导入脚本和测试脚本。

MAP-Bench：Multi-model Analytical Processing Benchmark。

也可以理解成 Multi-model Analytics Pipeline，因为负载是通过不同子查询的查询分析流水线组织起来的。

Map（地图/映射）暗示了连接和导航。Benchmark 的核心是将不同模型连接起来，像地图一样展示多模数据之间的关联。

## 目录概览

仓库根目录当前包含以下主要内容：

- `script/`：所有导入、查询、统计与辅助脚本。

`script/` 下的主要子目录如下：

- `script/common/`：各系统共享的通用脚本、统计脚本、绘图脚本以及多数据集参数配置文件。
- `script/arangodb/`：ArangoDB 的导入脚本与查询脚本。
- `script/agensgraph/`：AgensGraph 的导入脚本与查询脚本。
- `script/duckdb/`：DuckDB 的导入脚本与查询脚本。
- `script/helmdb/`：HelmDB 的导入脚本与查询脚本。
- `script/polystore/`：Polystore 的导入、查询与容器辅助脚本。

各系统目录通常都包含两个子目录：

- `load/`：负责建表/建集合、导入数据、创建索引、统计存储大小。
- `query/`：负责端到端延迟、资源占用、查询复杂度、执行计划等测试。

更详细的使用方式分别见：

- [ArangoDB Load](script/arangodb/load/README.md) / [ArangoDB Query](script/arangodb/query/README.md)
- [AgensGraph Load](script/agensgraph/load/README.md) / [AgensGraph Query](script/agensgraph/query/README.md)
- [DuckDB Load](script/duckdb/load/README.md) / [DuckDB Query](script/duckdb/query/README.md)
- [HelmDB Load](script/helmdb/load/README.md) / [HelmDB Query](script/helmdb/query/README.md)
- [Polystore Load](script/polystore/load/README.md) / [Polystore Query](script/polystore/query/README.md)

## 依赖

当前脚本的依赖如下：

```bash
pip install psycopg2-binary==2.9.8 python-arango==7.3.1 duckdb==1.2.2 "psycopg[binary]==3.2.11"
```

脚本已在 Python 3.13.0 下进行测试。

另外需要特别说明：由于客户端限制，HelmDB 查询相关脚本使用的 Python 版本是 **3.6.8**。

## 导入数据

各系统的详细导入说明已拆分到对应 `load/README.md` 中。下面保留原有的总览说明。

### arangodb 3.12.7

在 `main.sh` 中填写对应的配置信息，执行即可，时间较长，建议挂一晚，建索引时可能超时，重新单独跑建索引即可。

更详细说明见：[script/arangodb/load/README.md](script/arangodb/load/README.md)

### helmdb 最新 helmdb-develop 分支 [地址](https://gitee.com/whudb/HELMDB)

要求先编译好 ldbc 插件，修改 `load_data.sql` 的数据路径，修改 `main.sh` 的配置信息，执行 `main.sh` 即可，时间较长，建议挂一晚。

更详细说明见：[script/helmdb/load/README.md](script/helmdb/load/README.md)

### agensgraph 2.16.0 + pgvector 0.6.2

要求安装 `pgvector` 插件和 `file_fdw` 插件（导数据用），修改 `load_data.sql` 的数据路径，修改 `main.sh` 的配置信息，执行 `main.sh` 即可，时间较长，建议挂一晚。

更详细说明见：[script/agensgraph/load/README.md](script/agensgraph/load/README.md)

### duckdb 1.2.2

会自动安装 `json`、`vss`、`duckpgq` 插件，修改 `load_data.sql` 的数据路径，修改 `main.sh` 的配置信息，执行 `main.sh` 即可，时间较长，建议挂一晚。

> duckpgq 暂时不支持高版本的 duckdb，目前最高只支持 1.2.2（1.3.2 也支持，但是 bug 非常多，非常不稳定）
>
> centos7 上使用 duckdb 可能需要自己编译高版本 glibc，如下：
> ```bash
> patchelf --set-interpreter /path/to/mylibc_2_31/lib/ld-linux-x86-64.so.2 \
         --set-rpath /path/to/mylibc_2_31/lib \
         duckdb
> ```
>
> 也可自己编译 duckdb + 各类插件（因为插件仍依赖高版本 glibc）。
>
> 如果不想自己编译，仓库提供 dockerfile 来生成镜像。

更详细说明见：[script/duckdb/load/README.md](script/duckdb/load/README.md)

### polystore 系统 关系：PostgresSQL 14.20 文档：MongoDB 6.0.26 图：Neo4j 5.24.2 向量：Milvus 2.3.4

在 `util` 目录运行如下脚本，使用 docker 拉取 polystore 集群：

```bash
docker compose up -d
```

安装如下依赖：

```bash
pip install pymongo==4.15.4 psycopg[binary]==3.2.11 neo4j==6.0.3 pymilvus==2.6.3 pandas==2.3.3
```

执行：

```bash
python script/polystore/load_data.py
```

更详细说明见：[script/polystore/load/README.md](script/polystore/load/README.md)

## 跑查询

各系统的详细查询说明已拆分到对应 `query/README.md` 中。下面保留原有的总览说明。

### arangodb 3.12.7

修改 `bench_arangodb.py` 中的 `client` 和 `db` 的配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到 csv 文件中。

更详细说明见：[script/arangodb/query/README.md](script/arangodb/query/README.md)

### helmdb 最新 helmdb-develop 分支 [地址](https://gitee.com/whudb/HELMDB)

修改 `bench_helmdb.py` 中的 `DB_CONF` 配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到 csv 文件中。

更详细说明见：[script/helmdb/query/README.md](script/helmdb/query/README.md)

### agensgraph 2.16.0 + pgvector 0.6.2

修改 `bench_agensgraph.py` 中的 `DB_CONF` 配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到 csv 文件中。

更详细说明见：[script/agensgraph/query/README.md](script/agensgraph/query/README.md)

### duckdb 1.2.2

修改 `bench_duckdb.py` 中的 `DB_CONF` 配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到 csv 文件中。

更详细说明见：[script/duckdb/query/README.md](script/duckdb/query/README.md)

### polystore 系统

修改 `bench_poly.py` 中的 `DB_CONF` 配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到 csv 文件中。

更详细说明见：[script/polystore/query/README.md](script/polystore/query/README.md)
