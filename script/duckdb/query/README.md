## 运行说明

- 在当前目录执行以下命令。
- 所有查询脚本均通过 `-d mapl|mapm|maps` 切换数据集；默认值为 `mapl`。
- 查询参数统一配置在 `../../common/benchmark_config.json`。
- `st` 使用默认线程配置；`mt` 使用 `-t 16`。
- 当前查询集排除：`G1.sql G3.sql V1.sql V2.sql`。

## 端到端延迟

`st`

```bash
python bench_duckdb.py sql/*.sql -d maps -n 5 -x G1.sql G3.sql V1.sql V2.sql -o "out/maps_st_$(date +%F_%T).csv"
```

`mt`

```bash
python bench_duckdb.py sql/*.sql -d maps -t 16 -n 5 -x G1.sql G3.sql V1.sql V2.sql -o "out/maps_mt_$(date +%F_%T).csv"
```

## 内存和 CPU 占用

`st`

```bash
python bench_duckdb_res.py sql/*.sql -d maps -n 5 -x G1.sql G3.sql V1.sql V2.sql -o "out/res_maps_st_$(date +%F_%T).csv"
```

`mt`

```bash
python bench_duckdb_res.py sql/*.sql -d maps -t 16 -n 5 -x G1.sql G3.sql V1.sql V2.sql -o "out/res_maps_mt_$(date +%F_%T).csv"
```

## 查询语句与查询计划节点信息

```bash
python bench_duckdb_info.py sql/*.sql -d maps -x G1.sql G3.sql V1.sql V2.sql -o "out/info_maps_$(date +%F_%T).csv"
```

## 查询计划与 profile 信息

`st`

```bash
python bench_duckdb_plan.py sql/*.sql -d maps -x G1.sql G3.sql V1.sql V2.sql --warmup 1 -o "out/plan_maps_st_$(date +%F_%T).txt"
```

`mt`

```bash
python bench_duckdb_plan.py sql/*.sql -d maps -t 16 -x G1.sql G3.sql V1.sql V2.sql --warmup 1 -o "out/plan_maps_mt_$(date +%F_%T).txt"
```

