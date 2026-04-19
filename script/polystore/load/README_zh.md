[English](README.md) | [中文](README_zh.md)

## 导入说明

- 当前目录负责 Polystore 各后端数据的导入以及存储规模统计。

## 目录文件说明

- `main.sh`：导入主入口。
- `load_data.py`：按后端类型把数据导入 PostgreSQL、MongoDB、Neo4j 和 Milvus。
- `get_size.py`：统计 Polystore 各模型的存储占用。

## 运行前需要修改的配置

当前 `load_data.py` 默认仍以单数据集方式工作。在运行前需要根据你的部署修改：

- `DB_NAME`
- `DATA_ROOT`
- `CONTAINER_DATA_ROOT`
- `TMP_ROOT`
- `CONTAINER_TMP_ROOT`

如果容器端口或认证信息与默认值不同，还需要检查文件顶部的连接配置。

## 导入流程

`main.sh` 的流程如下：

1. 先执行 `python load_data.py -c` 创建 Polystore 中对应的数据集库。
2. 再并发执行：
   - `python load_data.py -p` 导入 PostgreSQL
   - `python load_data.py -m` 导入 MongoDB
   - `python load_data.py -n` 导入 Neo4j
   - `python load_data.py -v` 导入 Milvus

## 执行方式

```bash
bash main.sh
```

如果需要单独导入某个后端，也可以直接运行：

```bash
python load_data.py -p
python load_data.py -m
python load_data.py -n
python load_data.py -v
```

## 前置依赖

- 先在 `util/` 中启动对应的 Polystore 容器栈。
- 安装 `pymongo`、`psycopg`、`neo4j`、`pymilvus`、`pandas` 等依赖。

## 备注

- 如果你使用的是多数据集容器栈，需要先切换到对应的数据集后再执行导入。
- 当前 `load_data.py` 尚未像 query 脚本一样通过 `-d` 统一切换数据集，因此仍需要手工修改配置常量。
