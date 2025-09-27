# openalex-bench


## 介绍

这是openalex-bench的脚本仓库，包括导入脚本和测试sql脚本

当前脚本的依赖如下：

```bash
pip install psycopg2-binary python-arango
```
脚本已在Python 3.6.8下进行测试

## 导入数据

### arangodb

在main.sh中填写对应的配置信息，执行即可，时间较长，建议挂一晚，建索引时可能超时，重新单独跑建索引即可

### helmdb

要求先编译好ldbc插件，修改load_data.sql的数据路径，执行main.sh即可，时间较长，建议挂一晚

### agensgraph+pgvector

要求安装pgvector插件和file_fdw插件(导数据用) ，修改load_data.sql的数据路径，执行main.sh即可，时间较长，建议挂一晚

## 跑查询

### arangodb

修改bench_arangodb.py中的client和db的配置信息，按注释执行即可，会输出中位数时间和每次运行时间到csv文件中

### helmdb

修改bench_helmdb.py中的DB_CONF配置信息，按注释执行即可，会输出中位数时间和每次运行时间到csv文件中