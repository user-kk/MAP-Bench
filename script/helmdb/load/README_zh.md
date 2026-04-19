[English](README.md) | [中文](README_zh.md)

## 导入说明

- 当前目录负责 HelmDB 的 schema 创建、数据导入、索引创建、图结构导入以及存储规模统计。

## 目录文件说明

- `main.sh`：导入主入口。
- `create_schema.sql`：创建基础 schema。
- `load_data.sql`：导入关系、文档和向量相关数据。
- `create_index.sql`：创建查询需要的索引。
- `load_graph.sql`：导入图相关结构。
- `get_size.py`：统计各模型的存储占用。

## 运行前需要修改的配置

在 `main.sh` 中根据你的环境修改：

- `port`
- `database`

同时需要在 `load_data.sql` 中修改原始数据路径。

## 前置依赖

- 使用最新 `helmdb-develop` 分支
- 预先编译好 `ldbc` 插件

## 导入流程

`main.sh` 的流程如下：

1. 用 `gsql` 执行 `create_schema.sql` 建表。
2. 用 `gsql` 执行 `load_data.sql` 导入主体数据。
3. 用 `gsql` 执行 `create_index.sql` 创建索引。
4. 用 `gsql` 执行 `load_graph.sql` 导入图结构。

## 执行方式

```bash
bash main.sh
```

## 备注

- HelmDB 查询脚本由于客户端限制使用 Python 3.6.8，但导入流程本身主要依赖 `gsql`。
- 多数据集导入时，请按数据集分别修改 `database` 和 `load_data.sql` 中的数据路径。
