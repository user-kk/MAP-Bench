[English](README.md) | [中文](README_zh.md)

## 导入说明

- 当前目录负责 DuckDB 的 schema 创建、数据导入、索引创建以及存储规模统计。

## 目录文件说明

- `main.sh`：导入主入口。
- `create_schema.sql`：创建关系表与图/向量相关对象。
- `load_data.sql`：导入原始数据。
- `create_index.sql`：创建查询需要的索引。
- `get_size.py`：统计各模型的存储占用。

## 运行前需要修改的配置

在 `main.sh` 中根据你的环境修改：

- `database_path`

同时需要在 `load_data.sql` 中修改原始数据路径。

## 导入流程

`main.sh` 的流程如下：

1. 执行 `create_schema.sql`。
2. 执行 `load_data.sql`。
3. 执行 `create_index.sql`。

## 执行方式

```bash
bash main.sh
```

## 备注

- 当前 benchmark 依赖 DuckDB 1.2.2。
- 如果平台环境较旧，可能还需要自行处理 glibc 兼容问题。
- 多数据集导入时，请按数据集分别修改 `database_path` 和 `load_data.sql` 中的数据路径。
