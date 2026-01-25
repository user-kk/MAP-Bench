## 端到端延迟

```bash
prlimit --rss=64424509440 \
taskset -c 66-87 \
python3 bench_duckdb.py sql/*.sql -x G1.sql G3.sql V1.sql V2.sql -t 12 -o "out/$(date +%F_%T).csv"
```

## 内存和cpu占用

```bash
python bench_duckdb_res.py sql/*.sql -x G1.sql G3.sql V1.sql -o "out/res_$(date +%F_%T).csv" -t 1
```
## 查询语句与查询计划信息

```bash
python bench_duckdb_info.py sql/*.sql -o "out/info_$(date +%F_%T).csv"
```