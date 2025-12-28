#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import os, time, random
import sys
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

# --------- 主逻辑 ---------
def A4(ctx: "Context", timer: Optional[MDTimer] = None) -> pd.DataFrame:
    """
    返回 2020-2025 最热主题下发文最多的 TOP 3 机构
    列：['institution_name', 'paper_cnt']
    """

    # 1. PostgreSQL：拿 2020-2025 年所有论文 id
    with ctx.pg_cursor as cur:
        with TimerPhase(timer, "r"):
            cur.execute("SELECT id FROM work WHERE publication_year BETWEEN 2020 AND 2025")
            work_ids = [int(row[0]) for row in cur.fetchall()]
    if not work_ids:
        return pd.DataFrame(columns=["institution_name", "paper_cnt"])

    # 2. MongoDB：通过临时集合找最热主题（避免超长 $in）
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
            {"$unwind": "$doc.topics"},
            {"$group": {
                "_id": "$doc.topics.id",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1, "_id": 1}},
            {"$limit": 1}
        ]
        with TimerPhase(timer, "d"):
            cursor = ctx.mongo_db["work_doc"].aggregate(pipeline, allowDiskUse=True)
            hot_row = next(cursor, None)
        if not hot_row:
            return pd.DataFrame(columns=["institution_name", "paper_cnt"])
        hot_topic_id = int(hot_row["_id"])
    

    # 3. Neo4j：在该主题+年份范围内，各机构（去重作者）论文数
    cypher = f"""
    MATCH (au:author_v)<-[:work_author_e]-(w:work_v)-[:work_topic_e]->(t:topic_v{{id: {hot_topic_id} }})
    WHERE w.publication_year >= 2020 - 5
    return DISTINCT au.id as a_id,w.id as w_id
    """
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher)
        author_ids = []
        work_ids = []
        for r in records:
            author_ids.append(int(r["a_id"]))
            work_ids.append(int(r["w_id"]))
    
    if not author_ids:
        return pd.DataFrame(columns=["institution_name", "paper_cnt"])
    
    with ctx.temp_pg_table('tmp_author_work') as cur:
        # 4.1 灌入论文 id
        cur.execute("CREATE TEMP TABLE tmp_author_work AS "
                    "SELECT * FROM unnest(%s::bigint[], %s::float[]) AS t(a_id,w_id)",
                    (author_ids,work_ids))
        sql = """
        WITH InstCount AS (
        SELECT a.institution_id::bigint AS inst_id, COUNT(1) AS paper_cnt
        FROM tmp_author_work aht join author a ON aht.a_id = a.id
        WHERE a.institution_id is not NULL
        GROUP BY a.institution_id
        ORDER BY COUNT(1) DESC,a.institution_id asc
        LIMIT 3
        ) 
        SELECT i.display_name AS institution_name, ic.paper_cnt
        FROM InstCount ic,
        institution i
        WHERE i.id = ic.inst_id
        ORDER BY ic.paper_cnt DESC,i.id asc
        """
        with TimerPhase(timer, "r"): 
            df = pd.read_sql(sql, ctx._pg_conn)
    
    # 5. 最终表
    return df


# --------- 入口 ---------
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = A4(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)