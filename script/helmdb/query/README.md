## 端到端延迟

```bash
/usr/bin/python3 bench_helmdb.py sql/*.sql -o "out/$(date +%F_%T).csv"  -x  G5.sql G6.sql G7.sql
```

## 内存和cpu占用

```bash
/usr/bin/python3 bench_helmdb_res.py sql/*.sql -o "out/res_$(date +%F_%T).csv"  -x  G5.sql G6.sql G7.sql
```

## 查询语句与查询计划节点信息

```bash
/usr/bin/python3 bench_helmdb_info.py sql/*.sql -o "out/info_$(date +%F_%T).csv" -x  G5.sql G6.sql G7.sql
```

## 查询语句与查询计划节点信息


```bash
/usr/bin/python3 bench_helmdb_plan.py sql/*.sql -o "out/plan_$(date +%F_%T).txt" --warmup 1 -x  G5.sql G6.sql G7.sql
```