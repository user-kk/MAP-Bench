[English](README.md) | [中文](README_zh.md)

## Usage

- Run the following commands inside this directory.
- Query parameters are configured in `../../common/benchmark_config.json`.
- The `-d mapl|mapm|maps` option only switches the query parameters and the `db_name` used by PostgreSQL, MongoDB, and Milvus; the default value is `mapl`.
- The Neo4j dataset is **not** switched automatically by `-d`; you must switch the underlying data volume or container stack manually before running the benchmarks.
- If your local proxy interferes with requests to `127.0.0.1/localhost`, prepend the following environment prefix to the command:

```bash
env NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= http_proxy= https_proxy= all_proxy=
```

## Manually Switching the Polystore Dataset

The following example switches the stack to `maps`:

```bash
cd ../util
sudo docker compose -p polystore -f docker/<current-dataset>/docker-compose.yml down
sudo docker compose -p polystore -f docker/maps/docker-compose.yml up -d
```

You can verify whether Neo4j has switched to the target dataset with:

```bash
sudo docker inspect neo4j --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}'
```

If the output contains `neo4j_data_maps` or `util_neo4j_data_maps`, Neo4j is using the `maps` dataset.

## End-to-End Latency

```bash
python bench_poly.py sql/*.py -d maps -n 5 -o "out/maps_$(date +%F_%T).csv"
```

## Resource Usage

Note: the `res` script calls `docker compose restart`, so `-f` must explicitly point to the compose file for the current dataset.

```bash
python bench_poly_res.py sql/*.py -d maps -n 5 -f ../util/docker/maps/docker-compose.yml -o "out/res_maps_$(date +%F_%T).csv"
```

## Per-Model Time Breakdown

```bash
python bench_poly_info.py sql/*.py -d maps -o "out/info_maps_$(date +%F_%T).csv"
```

## Polyglot Persistent Execution Strategy

This implementation simulates an efficient polyglot persistent system and tries to minimize network communication overhead as much as possible.

- Cross-system materialization and pushdown:
    - When an intermediate result is large, it may be inefficient to keep the computation in memory. In this case, the intermediate result is materialized into the target model database (for example as a temporary table, document, or graph node), and that database completes the remaining join locally.
        - For example, A1 and A4 first filter results in PostgreSQL, then insert the intermediate result into a temporary MongoDB collection, and finally use `$lookup`-style joins inside MongoDB.
        - This approach is usually slower because cross-system transfer and format conversion costs are high.
    - When the intermediate result requires model-specific functionality, the result is materialized into the database that is best suited for the remaining operation.
        - For example, A2 materializes into MongoDB because Neo4j is not ideal for the required deeply nested processing.
        - H3 materializes into PostgreSQL because Milvus can only compute vector distance, while H3 needs a final score that combines distance with additional logic.
        - Performance is moderate and depends on both the target system capability and the migration cost.
- Application-level semi-join:
    - When the intermediate result is small or moderate and consists of a single column (typically an id list), the ids are embedded directly into the downstream query, and the application only performs light post-processing if needed.
        - Examples: A3, A6, H2, V1, V2, V3.
        - This approach is usually efficient because it makes good use of each system's optimizer while avoiding unnecessary data transfer.
    - When the intermediate result is small or moderate but contains multiple columns, the join keys (typically ids) are extracted and pushed down to downstream systems, while the application layer performs the final join or higher-level combination logic.
        - Examples: A5, G1, G2, G3, H1, H4, H5, V4.
        - Performance is moderate and depends on the middleware processing cost and the size of intermediate results.
