[English](README.md) | [中文](README_zh.md)

## 导入说明

- 当前目录负责 ArangoDB 的 schema 创建、数据导入、索引创建以及存储规模统计。
- 如果你希望保留英文版本，请使用顶部语言切换链接。

## 目录文件说明

- `main.sh`：导入主入口，负责预处理、建库对象、导入数据和建索引。
- `create_schema.js`：创建集合、图和向量集合。
- `create_index.js`：创建查询需要的索引。
- `get_size.py`：统计各模型的存储占用。
- `preproc/`：将原始 CSV 预处理成适合 `arangoimport` 的 JSONL 文件。

## 运行前需要修改的配置

在 `main.sh` 中根据你的环境修改：

- `username`
- `password`
- `database`
- `thread_num`
- `force_rebuild`
- `build_dir`
- `data_dir`

其中：
- `build_dir` 用于存放预处理生成的中间 JSONL 文件。
- `data_dir` 应指向当前数据集的根目录。

## 导入流程

`main.sh` 的流程如下：

1. 检查 `arangosh`、`arangoimport`、`python3` 是否可用。
2. 执行 `preproc/` 中的脚本，把文档、图和向量数据预处理成 JSONL。
3. 执行 `create_schema.js` 创建集合和图结构。
4. 使用 `arangoimport` 分批导入关系、文档、图和向量数据。
5. 执行 `create_index.js` 创建索引。

## 执行方式

```bash
bash main.sh
```

## 备注

- 大数据集导入时间较长，建议长时间后台运行。
- 建索引阶段如果超时，可以单独重新执行 `create_index.js`。
- 多数据集导入时，请按数据集分别修改 `database`、`build_dir` 和 `data_dir`。
