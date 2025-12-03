## 端到端延迟

```bash
python bench_agensgraph.py sql/*.sql -o "out/$(date +%F_%T).csv" -x G1.sql
```

## 内存和cpu占用

```bash
python bench_agensgraph_res.py sql/*.sql -o "out/$(date +%F_%T).csv" -x G1.sql
```