[English](README.md) | [中文](README_zh.md)

## Usage

- Run the following commands inside this directory.
- All query scripts support dataset switching through `-d mapl|mapm|maps`; the default value is `mapl`.
- Query parameters are configured in `../../common/benchmark_config.json`.
- If your local proxy interferes with requests to `127.0.0.1/localhost`, prepend the following environment prefix to the command:

```bash
env NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= http_proxy= https_proxy= all_proxy=
```

## End-to-End Latency

```bash
python bench_arangodb.py sql/*.aql -d maps -n 5 -o "out/maps_$(date +%F_%T).csv"
```

## Resource Usage

Note: the `res` script restarts the `arangodb` service before each workload, so the full run may take a long time.

```bash
python bench_arangodb_res.py sql/*.aql -d maps -n 5 -o "out/res_maps_$(date +%F_%T).csv"
```

## Query Tokens and Plan Node Statistics

```bash
python bench_arangodb_info.py sql/*.aql -d maps -o "out/info_maps_$(date +%F_%T).csv"
```

## Query Plans and Profile Output

```bash
python bench_arangodb_plan.py sql/*.aql -d maps --warmup 1 -o "out/plan_maps_$(date +%F_%T).txt"
```
