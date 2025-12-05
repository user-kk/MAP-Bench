## 端到端延迟

```bash
python bench_duckdb.py sql/*.sql -x G1.sql G3.sql -o "out/$(date +%F_%T).csv"
```

## 内存和cpu占用

```bash
python bench_duckdb_res.py sql/*.sql -x G1.sql G3.sql -o "out/res_$(date +%F_%T).csv"
```
## 查询语句与查询计划信息

```bash
python bench_duckdb_info.py sql/*.sql -o "out/info_$(date +%F_%T).csv"
```