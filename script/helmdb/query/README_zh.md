[English](README.md) | [中文](README_zh.md)

## 运行说明

- 在当前目录执行以下命令。
- 所有查询脚本均通过 `-d mapl|mapm|maps` 切换数据集；默认值为 `mapl`。
- 查询参数统一配置在 `../../common/benchmark_config.json`。
- 当前查询集排除：`G5.sql G6.sql G7.sql`。
- 如果你的部署要求使用特定用户或解释器（例如系统 Python），请自行切换到对应用户或解释器后再执行以下命令。

## 端到端延迟

```bash
python bench_helmdb.py sql/*.sql -d maps -n 5 -x G5.sql G6.sql G7.sql -o "out/maps_$(date +%F_%T).csv"
```

## 内存和 CPU 占用

说明：`res` 脚本会在每个 workload 前重启 `openGauss` 服务，整套测试耗时较长。

```bash
python bench_helmdb_res.py sql/*.sql -d maps -n 5 -x G5.sql G6.sql G7.sql -o "out/res_maps_$(date +%F_%T).csv"
```

## 查询语句与查询计划节点信息

```bash
python bench_helmdb_info.py sql/*.sql -d maps -x G5.sql G6.sql G7.sql -o "out/info_maps_$(date +%F_%T).csv"
```

## 查询计划与 profile 信息

```bash
python bench_helmdb_plan.py sql/*.sql -d maps --warmup 1 -x G5.sql G6.sql G7.sql -o "out/plan_maps_$(date +%F_%T).txt"
```
