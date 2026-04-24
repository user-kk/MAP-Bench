[English](README.md) | [中文](README_zh.md)

## Usage

- Run the following commands inside this directory.
- All query scripts support dataset switching through `-d mapl|mapm|maps`; the default value is `mapl`.
- Query parameters are configured in `../../common/benchmark_config.json`.
- `st` uses the default thread setting; `mt` uses `-t 16`.
- The following queries are currently excluded: `G1.sql G3.sql V1.sql V2.sql`.

## End-to-End Latency

`st`

```bash
python bench_duckdb.py sql/*.sql -d maps -n 5 -x G1.sql G3.sql V1.sql V2.sql -o "out/maps_st_$(date +%F_%T).csv"
```

`mt`

```bash
python bench_duckdb.py sql/*.sql -d maps -t 16 -n 5 -x G1.sql G3.sql V1.sql V2.sql -o "out/maps_mt_$(date +%F_%T).csv"
```

## Resource Usage

`st`

```bash
python bench_duckdb_res.py sql/*.sql -d maps -n 5 -x G1.sql G3.sql V1.sql V2.sql -o "out/res_maps_st_$(date +%F_%T).csv"
```

`mt`

```bash
python bench_duckdb_res.py sql/*.sql -d maps -t 16 -n 5 -x G1.sql G3.sql V1.sql V2.sql -o "out/res_maps_mt_$(date +%F_%T).csv"
```

## Query Tokens and Plan Node Statistics

```bash
python bench_duckdb_info.py sql/*.sql -d maps -x G1.sql G3.sql V1.sql V2.sql -o "out/info_maps_$(date +%F_%T).csv"
```

## Query Plans and Profile Output

`st`

```bash
python bench_duckdb_plan.py sql/*.sql -d maps -x G1.sql G3.sql V1.sql V2.sql --warmup 1 -o "out/plan_maps_st_$(date +%F_%T).txt"
```

`mt`

```bash
python bench_duckdb_plan.py sql/*.sql -d maps -t 16 -x G1.sql G3.sql V1.sql V2.sql --warmup 1 -o "out/plan_maps_mt_$(date +%F_%T).txt"
```
