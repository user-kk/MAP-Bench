## 端到端延迟

```bash
/usr/bin/python3 bench_helmdb.py sql/*.sql -o "out/$(date +%F_%T).csv"  -x  G4.sql G5.sql G6.sql 
```

## 内存和cpu占用

```bash
/usr/bin/python3 bench_helmdb_res.py sql/*.sql -o "out/$(date +%F_%T).csv"  -x  G4.sql G5.sql G6.sql 
```

