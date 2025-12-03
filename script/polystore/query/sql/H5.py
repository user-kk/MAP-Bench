#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context

def H5(ctx: "Context",
       a_id: int = 4395661325,
       b_id: int = 4316345068,
       topic_id: int = 10039) -> pd.DataFrame:
    """
    两篇文章最短路径上的中间论文（不含起点/终点），
    按主题向量距离升序 + 引用数降序取前 3。
    返回：id, title, authors, topics, cited_by_count
    """
    # 1. Neo4j：最短路径节点（去掉起点/终点）
    cypher = """
    MATCH sp = shortestPath(
        (a:work_v {id: $a_id})-[:work_referenced_work_e*]->(b:work_v {id: $b_id})
    )
    WITH nodes(sp) AS nds
    UNWIND nds AS mid
    WITH mid
    WHERE mid.id <> $a_id AND mid.id <> $b_id
    RETURN mid.id AS w_id
    """
    records = ctx.neo4j_session.run(cypher, a_id=a_id, b_id=b_id)
    path_ids =[int(r["w_id"]) for r in records]
    if len(path_ids) == 0:
        return pd.DataFrame(columns=['id', 'title', 'authors', 'topics', 'cited_by_count'])

    # 2. Milvus：向量距离（L2 升序）
    topic_coll = ctx.get_milvus_collection("topic_vec")
    work_coll  = ctx.get_milvus_collection("work_vec")

    topic_vec = topic_coll.query(expr=f"id=={topic_id}", output_fields=["vec"])[0]["vec"]
    
    hits = work_coll.search(
            data=[topic_vec],
            anns_field="vec",
            param={"metric_type": "L2"},
            limit=len(path_ids),
            expr=f"id in {path_ids}"
        )[0]


    # 按距离升序、id 升序排
    hit_map = {int(h.id): h.distance for h in hits}
    df_vec = pd.DataFrame({"id": path_ids, "vec_dist": [hit_map.get(wid) for wid in path_ids]}).sort_values(["vec_dist", "id"]).head(3)

    # 3. PostgreSQL：补齐 title / cited_by_count
    id_place = ",".join(["%s"] * len(df_vec))
    sql = f"SELECT id, title, cited_by_count FROM work WHERE id IN ({id_place})"
    df_pg = pd.read_sql(sql, ctx._pg_conn, params=df_vec["id"].tolist())

    # 4. MongoDB：聚合管道拿 authors & topics
    ref_ids = df_vec["id"].tolist()
    pipe = [
        {"$match": {"_id": {"$in": ref_ids}}},
        {"$project": {
            "_id": 1,
            "authors": "$doc.authorships.author.display_name",
            "topics": "$doc.topics.display_name"
        }}
    ]
    cursor = ctx.mongo_db["work_doc"].aggregate(pipe)
    id2authors = {}
    id2topics  = {}
    for doc in cursor:
        wid = doc["_id"]
        id2authors[wid] = str(doc.get("authors", []))
        id2topics[wid]  = str(doc.get("topics", []))

    # 5. 合并
    df = (df_vec.drop(columns=["vec_dist"])
                .merge(df_pg, on="id")
                .assign(authors=lambda x: x["id"].map(id2authors),
                        topics=lambda x: x["id"].map(id2topics))
                .reindex(columns=['id', 'title', 'authors', 'topics', 'cited_by_count']))
    return df


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(H5(ctx))