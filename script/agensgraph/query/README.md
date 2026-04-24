[English](README.md) | [中文](README_zh.md)

## Usage

- Run the following commands inside this directory.
- All query scripts support dataset switching through `-d mapl|mapm|maps`; the default value is `mapl`.
- Query parameters are configured in `../../common/benchmark_config.json`.
- `sp` corresponds to `-t 0`, and `mp` corresponds to `-t 16`.

## End-to-End Latency

`sp`

```bash
python bench_agensgraph.py sql/*.sql -d maps -t 0 -n 5 -o "out/maps_sp_$(date +%F_%T).csv"
```

`mp`

```bash
python bench_agensgraph.py sql/*.sql -d maps -t 16 -n 5 -o "out/maps_mp_$(date +%F_%T).csv"
```

## Resource Usage

Note: the `res` script restarts the `agensgraph` service before each workload, so the full run may take a long time.

`sp`

```bash
python bench_agensgraph_res.py sql/*.sql -d maps -p 0 -n 5 -o "out/res_maps_sp_$(date +%F_%T).csv"
```

`mp`

```bash
python bench_agensgraph_res.py sql/*.sql -d maps -p 16 -n 5 -o "out/res_maps_mp_$(date +%F_%T).csv"
```

## Query Tokens and Plan Node Statistics

```bash
python bench_agensgraph_info.py sql/*.sql -d maps -o "out/info_maps_$(date +%F_%T).csv"
```

## Query Plans and Profile Output

`sp`

```bash
python bench_agensgraph_plan.py sql/*.sql -d maps -t 0 --warmup 1 -o "out/plan_maps_sp_$(date +%F_%T).txt"
```

`mp`

```bash
python bench_agensgraph_plan.py sql/*.sql -d maps -t 16 --warmup 1 -o "out/plan_maps_mp_$(date +%F_%T).txt"
```
