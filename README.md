# MAP-Bench

<div align="center">
    <img src="logo.svg" width="300" alt="Logo" />
</div>

## 介绍

这是MAP-Bench的脚本仓库，包括导入脚本和测试sql脚本

MAP-Bench：Multi-model Analytical Processing Benchmark

也可以理解成Multi-model Analytics Pipeline，因为负载是通过不同子查询的查询分析流水线组织起来的

Map(地图/映射) 暗示了连接和导航。 Benchmark 的核心是将不同模型连接起来，像地图一样展示多模数据之间的关联

### 依赖
当前脚本的依赖如下：

```bash
pip install psycopg2-binary==2.9.8 python-arango==7.3.1 duckdb==1.2.2 "psycopg[binary]==3.2.11"
```
脚本已在Python 3.13.0下进行测试

## 导入数据

### arangodb 3.12.7

在main.sh中填写对应的配置信息，执行即可，时间较长，建议挂一晚，建索引时可能超时，重新单独跑建索引即可

### helmdb 最新helmdb-develop分支 [地址](https://gitee.com/whudb/HELMDB) 

要求先编译好ldbc插件，修改load_data.sql的数据路径，修改main.sh的配置信息，执行main.sh即可，时间较长，建议挂一晚

### agensgraph 2.16.0 + pgvector 0.6.2

要求安装pgvector插件和file_fdw插件(导数据用) ，修改load_data.sql的数据路径，修改main.sh的配置信息，执行main.sh即可，时间较长，建议挂一晚

### duckdb 1.2.2 

会自动安装json、vss、duckpgq插件，修改load_data.sql的数据路径，修改main.sh的配置信息，执行main.sh即可，时间较长，建议挂一晚

> duckpgq暂时不支持高版本的duckdb，目前最高只支持1.2.2(1.3.2 也支持，但是bug非常多，非常不稳定)
>
> centos7上使用duckdb可能需要自己编译高版本glibc,如下：
> ```bash
>  patchelf --set-interpreter /path/to/mylibc_2_31/lib/ld-linux-x86-64.so.2 \
>           --set-rpath /path/to/mylibc_2_31/lib \
>           duckdb
> ```
>
> 也可自己编译duckdb+各类插件(因为插件仍依赖高版本glibc)
>
> 如果不想自己编译,仓库提供dockerfile来生成镜像 

### polystore系统 关系：PostgresSQL 14.20 文档：MongoDB 6.0.26 图：Neo4j 5.24.2 向量：Milvus 2.3.4

在util目录运行如下脚本，使用docker拉取polystore集群
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

## 跑查询

### arangodb 3.12.7

修改bench_arangodb.py中的client和db的配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到csv文件中

### helmdb 最新helmdb-develop分支 [地址](https://gitee.com/whudb/HELMDB) 

修改bench_helmdb.py中的DB_CONF配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到csv文件中

### agensgraph 2.16.0 + pgvector 0.6.2

修改bench_agensgraph.py中的DB_CONF配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到csv文件中

### duckdb 1.2.2 

修改bench_duckdb.py中的DB_CONF配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到csv文件中

### polystore系统

修改bench_poly.py中的DB_CONF配置信息，按注释执行即可，会实时刷新中位数时间和每次运行时间到csv文件中