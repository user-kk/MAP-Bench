## 端到端延迟

```bash
python bench_arangodb.py sql/*.aql -o "out/$(date +%F_%T).csv"
```

## 内存和cpu占用

```bash
python bench_arangodb_res.py sql/*.aql -o "out/res_$(date +%F_%T).csv"
```

## 查询语句与查询计划节点信息

```bash
python bench_arangodb_info.py sql/*.aql -o "out/info_$(date +%F_%T).csv"
```

## 查询计划与profile信息

```bash
python bench_arangodb_plan.py sql/*.aql --warmup 1 -o "out/plan_$(date +%F_%T).txt"
```