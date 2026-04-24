[English](README.md) | [中文](README_zh.md)

## Usage

- Run the following commands inside this directory.
- All query scripts support dataset switching through `-d mapl|mapm|maps`; the default value is `mapl`.
- Query parameters are configured in `../../common/benchmark_config.json`.
- The following queries are currently excluded: `G5.sql G6.sql G7.sql`.
- If your deployment requires a specific user account or Python interpreter (for example, a system Python), switch to that user/interpreter before running the commands below.

## End-to-End Latency

```bash
python bench_gredodb.py sql/*.sql -d maps -n 5 -x G5.sql G6.sql G7.sql -o "out/maps_$(date +%F_%T).csv"
```

## Resource Usage

Note: the `res` script restarts the `openGauss` service before each workload, so the full run may take a long time.

```bash
python bench_gredodb_res.py sql/*.sql -d maps -n 5 -x G5.sql G6.sql G7.sql -o "out/res_maps_$(date +%F_%T).csv"
```

## Query Tokens and Plan Node Statistics

```bash
python bench_gredodb_info.py sql/*.sql -d maps -x G5.sql G6.sql G7.sql -o "out/info_maps_$(date +%F_%T).csv"
```

## Query Plans and Profile Output

```bash
python bench_gredodb_plan.py sql/*.sql -d maps --warmup 1 -x G5.sql G6.sql G7.sql -o "out/plan_maps_$(date +%F_%T).txt"
```
