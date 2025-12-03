## 端到端延迟

```bash
python bench_duckdb.py sql/*.sql -x G1.sql G3.sql -o "out/$(date +%F_%T).csv"
```

## 内存和cpu占用

```bash
python bench_duckdb_res.py sql/*.sql -x G1.sql G3.sql -o "out/$(date +%F_%T).csv"
```
