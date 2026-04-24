[English](README.md) | [中文](README_zh.md)

## 运行说明

- 在当前目录执行以下命令。
- 查询参数统一配置在 `../../common/benchmark_config.json`。
- 脚本中的 `-d mapl|mapm|maps` 只负责切换查询参数以及 `PG/MongoDB/Milvus` 侧的 `db_name`；默认值为 `mapl`。
- `Neo4j` 数据集不会由 `-d` 自动切换，必须先手动切到对应的数据卷或容器栈。
- 如果本地代理会影响 `127.0.0.1/localhost` 的请求，可在命令前添加以下前缀：

```bash
env NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= http_proxy= https_proxy= all_proxy=
```

## 手动切换 Polystore 数据集

以下以切到 `maps` 为例：

```bash
cd ../util
sudo docker compose -p polystore -f docker/<当前数据集>/docker-compose.yml down
sudo docker compose -p polystore -f docker/maps/docker-compose.yml up -d
```

可以用下面的命令确认 `Neo4j` 是否已经切到目标数据集：

```bash
sudo docker inspect neo4j --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}'
```

如果输出包含 `neo4j_data_maps` 或 `util_neo4j_data_maps`，说明当前 `Neo4j` 已切到 `maps`。

## 端到端延迟

```bash
python bench_poly.py sql/*.py -d maps -n 5 -o "out/maps_$(date +%F_%T).csv"
```

## 资源占用

说明：`res` 脚本会调用 `docker compose restart`，因此 `-f` 需要显式传入当前数据集对应的 compose 文件。

```bash
python bench_poly_res.py sql/*.py -d maps -n 5 -f ../util/docker/maps/docker-compose.yml -o "out/res_maps_$(date +%F_%T).csv"
```

## 各模型时间占比

```bash
python bench_poly_info.py sql/*.py -d maps -o "out/info_maps_$(date +%F_%T).csv"
```

## polyglot persistent实现策略：模拟高效的polyglot persistent系统，最大化的减少网络通信的开销
- 跨系统物化与下推：
    - 当中间临时结果较大时，不适合放在内存中计算，把中间临时结果物化到某一模型的数据库中(作为临时表/文档/图节点)，让该模型数据库自身来通过join完成计算 
	    - 例如：A1、A4 需要在pg中过滤结果，同时插入到mongodb的临时集合中，mongodb在通过$lookup（类似于join）查临时表与自身数据join后做聚集操作
	    - 性能较差，主要由于跨系统数据传输与转换开销较大。
    - 当中间结果涉及特定模型的操作时，把中间临时结果物化到某一模型的数据库中，利用指定数据库的能力完成计算
	    - 例如：A2 neo4j不好处理深层嵌套数据，把结果物化到mongodb来做 
	    - H3 milvus只能计算向量距离，但H3需要一个包含向量距离的综合评分，所以把结果物化到pg来做
	    - 性能中等，取决于目标系统的处理能力与数据迁移成本。
- 应用层半连接:
    - 当中间结果较小或一般时且为单列时（一般为id列表）
        - 直接内嵌到查询语句的in子句中，发给对应数据库，获得所涉及模型的结果后根据查询要求做简单处理或不做处理 
        - 例如：A3 A6 H2 V1 V2 V3 
        - 性能优秀，充分利用各系统的查询优化能力，避免不必要的数据传输。
    - 当中间结果较小或一般时且为多列时，拆分出join要用到的列（一般为id列表），发给对应数据库(内嵌到查询语句的in子句中)，
		获得查询结果后直接在中间层完成完整的join操作或进行其他复杂处理（类似于分布式的半连接操作）
        - 例如：A5 G1 G2 G3 H1 H4 H5 V4 
        - 性能中等，取决于中间层的处理效率与数据规模。
