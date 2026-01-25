## 端到端延迟

```bash
python bench_agensgraph.py sql/*.sql -o "out/$(date +%F_%T).csv" -t 0
python bench_agensgraph.py sql/*.sql -o "out/$(date +%F_%T).csv" -t 12
```

## 内存和cpu占用

```bash
python bench_agensgraph_res.py sql/*.sql -o "out/res_$(date +%F_%T).csv"
```

## 查询语句与查询计划信息

```bash
python bench_agensgraph_info.py sql/*.sql -o "out/info_$(date +%F_%T).csv"
```
