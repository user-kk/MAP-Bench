## 端到端延迟

```bash
python bench_arangodb.py sql/*.aql -o "out/$(date +%F_%T).csv"
```

## 内存和cpu占用

```bash
python bench_arangodb_res.py sql/*.aql -o "out/$(date +%F_%T).csv"
```
