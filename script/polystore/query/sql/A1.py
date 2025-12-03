#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import os, time, random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context

# --------- 主逻辑 ---------
def A1(ctx: "Context") -> pd.DataFrame:
    """
    返回 近5年发文最多的 TOP 3 机构，以及每个机构发文最多的 TOP 3 主题
    列：['institution_name', 'topic', 'freq']
    """

    # 1. PostgreSQL：2024-2025 年所有论文 id
    with ctx.pg_cursor as cur:
        cur.execute("SELECT id FROM work WHERE publication_year >= 2024-5")
        work_ids = [int(row[0]) for row in cur.fetchall()]
        if not work_ids:
            return pd.DataFrame(columns=["institution_name", "topic", "freq"])

    # 2. MongoDB：通过临时集合找发文最多的机构
    with ctx.temp_mongo_collection() as tmp_col:
        tmp_col.insert_many([{"_id": wid} for wid in work_ids])
        pipeline = [
            {"$lookup": {
                "from": tmp_col.name,
                "localField": "_id",
                "foreignField": "_id",
                "as": "hit"
            }},
            {"$match": {"hit": {"$ne": []}}},
            {"$unwind": "$doc.authorships"},
            {"$match": {
                "doc.authorships.institution.id": {"$exists": True, "$ne": None}
            }},
            {"$group": {
                "_id": "$doc.authorships.institution.id",
                "papers_cnt": {"$sum": 1}
            }},
            {"$sort": {"papers_cnt": -1, "_id": 1}},
            {"$limit": 3}
        ]
        cursor = ctx.mongo_db["work_doc"].aggregate(pipeline, allowDiskUse=True)
        top_institutions = list(cursor)
        if not top_institutions:
            return pd.DataFrame(columns=["institution_name", "topic", "freq"])
    
    # 3. PostgreSQL：拿这些机构下所有作者 id
    
    with ctx.pg_cursor as cur:
        top_institutions_ids = [int(doc["_id"]) for doc in top_institutions]
        id_place = ",".join(["%s"] * len(top_institutions_ids))
        cur.execute(f"SELECT id,institution_id FROM author a WHERE institution_id in ({id_place})", tuple(top_institutions_ids))
        author_insts = [{"aid":int(row[0]),"inst_id":int(row[1])} for row in cur.fetchall()]
        if not author_insts:
            return pd.DataFrame(columns=["institution_name", "topic", "freq"])

    

    # 4. Neo4j：获得每个机构作者在该时间段内各主题的发文数最多的前 3 个主题
    
    cypher = """
    UNWIND $rows AS k
    MATCH (a:author_v)<-[:work_author_e]-(w:work_v)-[:work_topic_e]->(t:topic_v)
    WHERE a.id = k.aid AND w.publication_year >= 2019   // 2024-5
    WITH k.inst_id AS inst_id, t.id AS topic_id,
        COUNT(w.id) AS freq
    ORDER BY inst_id, freq DESC        // 同一机构内按 freq 倒序排，后面 collect 顺序才有保证
    WITH inst_id,
        collect({topic_id: topic_id, freq: freq})[0..3] AS top3
    UNWIND top3 AS t                   // 拆回多行
    RETURN inst_id AS inst_id,
        t.topic_id AS topic_id,
        t.freq      AS freq
    ORDER BY inst_id, freq DESC
    """
    records = ctx.neo4j_session.run(cypher, rows=author_insts)
    df = pd.DataFrame([dict(r) for r in records])
    print(df)
    # 显式指定列名，确保顺序和后面 sql 对应
    df = df[["inst_id", "topic_id", "freq"]]

    # 5. PostgreSQL：补齐机构名称 & 主题名称
    sql = """
        SELECT inst.display_name AS institution_name,
               top.display_name AS topic,
               t.freq AS freq
        FROM unnest(%s::bigint[],%s::bigint[],%s::bigint[]) as t(instid,topicid,freq)
        LEFT JOIN institution inst ON t.instid = inst.id
        LEFT JOIN topic top ON t.topicid = top.id

    """
    
    out = pd.read_sql(
            sql,
            ctx._pg_conn,
            params=(df["inst_id"].tolist(), df["topic_id"].tolist(), df["freq"].tolist())
        )
    return out


# --------- 入口 ---------
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(A1(ctx))