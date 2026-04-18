## 运行说明

- 在当前目录执行以下命令。
- 所有查询脚本均通过 `-d mapl|mapm|maps` 切换数据集；默认值为 `mapl`。
- 查询参数统一配置在 `../../common/benchmark_config.json`。
- 如果本地代理会影响 `127.0.0.1/localhost` 的请求，可在命令前添加以下前缀：

```bash
env NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= http_proxy= https_proxy= all_proxy=
```

## 端到端延迟

```bash
python bench_arangodb.py sql/*.aql -d maps -n 5 -o "out/maps_$(date +%F_%T).csv"
```

## 资源占用

说明：`res` 脚本会在每个 workload 前重启 `arangodb` 服务，整套测试耗时较长。

```bash
python bench_arangodb_res.py sql/*.aql -d maps -n 5 -o "out/res_maps_$(date +%F_%T).csv"
```

## 查询语句与查询计划节点信息

```bash
python bench_arangodb_info.py sql/*.aql -d maps -o "out/info_maps_$(date +%F_%T).csv"
```

## 查询计划与 profile 信息

```bash
python bench_arangodb_plan.py sql/*.aql -d maps --warmup 1 -o "out/plan_maps_$(date +%F_%T).txt"
```

