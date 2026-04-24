[English](README.md) | [中文](README_zh.md)

## 运行说明

- 在当前目录执行以下命令。
- 所有查询脚本均通过 `-d mapl|mapm|maps` 切换数据集；默认值为 `mapl`。
- 查询参数统一配置在 `../../common/benchmark_config.json`。
- `sp` 对应 `-t 0`，`mp` 对应 `-t 12`。

## 端到端延迟

`sp`

```bash
python bench_agensgraph.py sql/*.sql -d maps -t 0 -n 5 -o "out/maps_sp_$(date +%F_%T).csv"
```

`mp`

```bash
python bench_agensgraph.py sql/*.sql -d maps -t 12 -n 5 -o "out/maps_mp_$(date +%F_%T).csv"
```

## 内存和 CPU 占用

说明：`res` 脚本会在每个 workload 前重启 `agensgraph` 服务，整套测试耗时较长。

`sp`

```bash
python bench_agensgraph_res.py sql/*.sql -d maps -p 0 -n 5 -o "out/res_maps_sp_$(date +%F_%T).csv"
```

`mp`

```bash
python bench_agensgraph_res.py sql/*.sql -d maps -p 12 -n 5 -o "out/res_maps_mp_$(date +%F_%T).csv"
```

## 查询语句与查询计划节点信息

```bash
python bench_agensgraph_info.py sql/*.sql -d maps -o "out/info_maps_$(date +%F_%T).csv"
```

## 查询计划与 profile 信息

`sp`

```bash
python bench_agensgraph_plan.py sql/*.sql -d maps -t 0 --warmup 1 -o "out/plan_maps_sp_$(date +%F_%T).txt"
```

`mp`

```bash
python bench_agensgraph_plan.py sql/*.sql -d maps -t 12 --warmup 1 -o "out/plan_maps_mp_$(date +%F_%T).txt"
```
