#!/usr/bin/env python3
import pandas as pd
import numpy as np
from pathlib import Path
import math
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from pymilvus import Collection

def V1(ctx: "Context",
       topic_name: str = "Impact of Climate Change on Human Health",
       top_k: int = 10) -> pd.DataFrame:

    
    pipeline = [
        {"$match": {"doc.topics.display_name": topic_name}},
        {"$project": {"_id": 1}}
    ]
    
    mongo_cursor = ctx.mongo_db["work_doc"].aggregate(pipeline)
    
    work_ids = [doc["_id"] for doc in mongo_cursor]
    
    
    work_ids_place = ",".join(["%s"] * len(work_ids))

    
    sql_top1 = f"""
    SELECT w.id
    FROM work w
    WHERE w.publication_year >= 2020 - 5
        AND w.id in ({work_ids_place})
    ORDER BY w.cited_by_count DESC, w.id ASC
    LIMIT 1
    """
    with ctx.pg_cursor as cur:
        cur.execute(sql_top1, tuple(work_ids))
        top_row = cur.fetchone()
    if not top_row:
        return pd.DataFrame(columns=['title', 'cited_by_count', 'similarity_score'])
    top_work_id = int(top_row[0])


    # 2. Neo4j：1-2 跳引用网络（去重）
    cypher = """
    MATCH (p1:work_v)-[:work_referenced_work_e*1..2]->(p2:work_v)
    WHERE p1.id = $wid
    RETURN DISTINCT p2.id AS cited_work_id
    """
    records = ctx.neo4j_session.run(cypher, wid=top_work_id)
    net_ids = [int(r["cited_work_id"]) for r in records]
    if not net_ids:
        return pd.DataFrame(columns=['title', 'cited_by_count', 'similarity_score'])

    # 3. Milvus：批量拉取向量
    work_collection = ctx.get_milvus_collection("work_vec")
    
    target_vec = work_collection.query(
        expr=f"id == {top_work_id}",
        output_fields=["vec"]
    )[0]["vec"]
    
    hits = work_collection.search(
            data=[target_vec],
            anns_field="vec",
            param={"metric_type": "L2"},
            limit=top_k,
            expr=f"id in {net_ids}"
        )[0]

    if not hits:
        return pd.DataFrame(columns=['title', 'cited_by_count', 'similarity_score'])

    # 5. PostgreSQL：回表补齐 title & cited_by_count
    sim_map = {int(h.id): math.sqrt(float(h.distance)) for h in hits}
    keys = list(sim_map.keys())
    id_place = ",".join(["%s"] * len(sim_map))
    sql_final = f"""
    SELECT id, title, cited_by_count
    FROM work
    WHERE id IN ({id_place})
    ORDER BY array_position(ARRAY[{id_place}], id)   -- 保持相似度顺序
    """
    df = pd.read_sql(sql_final, ctx._pg_conn, params=keys+keys)
    df["similarity_score"] = df["id"].map(sim_map)
    return df[['title', 'cited_by_count', 'similarity_score']].reset_index(drop=True)


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(V1(ctx))