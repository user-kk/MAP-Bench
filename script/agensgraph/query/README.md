## 端到端延迟

```bash
python bench_agensgraph.py sql/*.sql -o "out/$(date +%F_%T).csv" -x G1.sql
```

## 内存和cpu占用

```bash
python bench_agensgraph_res.py sql/*.sql -o "out/res_$(date +%F_%T).csv" -x G1.sql
```

## 查询语句与查询计划信息

```bash
python bench_agensgraph_info.py sql/*.sql -o "out/info_$(date +%F_%T).csv"
```
