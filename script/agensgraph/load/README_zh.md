[English](README.md) | [中文](README_zh.md)

## 导入说明

- 当前目录负责 AgensGraph 的 schema 创建、数据导入、索引创建以及存储规模统计。

## 目录文件说明

- `main.sh`：导入主入口。
- `create_schema.sql`：创建表、图标签和边结构。
- `load_data.sql`：导入关系、文档、图和向量相关数据。
- `create_index.sql`：创建查询所需索引。
- `get_size.py`：统计各模型的存储占用。

## 运行前需要修改的配置

在 `main.sh` 中根据你的环境修改：

- `port`
- `user`
- `database`
- `psql_path`

同时需要在 `load_data.sql` 中修改原始数据路径。

## 前置依赖

- 安装 `pgvector`
- 安装 `file_fdw`

## 导入流程

`main.sh` 的流程如下：

1. 使用 `create_schema.sql` 创建 schema。
2. 使用 `load_data.sql` 导入数据。
3. 使用 `create_index.sql` 创建索引。

## 执行方式

```bash
bash main.sh
```

## 备注

- 导入和建索引耗时都可能较长，建议长时间后台运行。
- 多数据集导入时，请按数据集分别修改 `database` 和 `load_data.sql` 中的数据路径。
