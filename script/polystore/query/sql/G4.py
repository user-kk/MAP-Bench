#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

def G4(ctx: "Context",
       topic1:str = 'Education',
       topic2:str = 'Computer Vision and Pattern Recognition',
       timer: Optional[MDTimer] = None) -> pd.DataFrame:
    """
    返回同时属于'Education'和'Computer Vision and Pattern Recognition'两个子领域、
    2022年发表、作者数≤3的TOP 20论文
    列：['id', 'title']
    """
    
    # 1. PostgreSQL：获取两个子领域的主题ID
    with ctx.pg_cursor as cur:
        with TimerPhase(timer, "r"):
            cur.execute(f"""
                SELECT id FROM topic 
                WHERE subfield_display_name = '{topic1}'
            """)
            topic_id1s = [int(row[0]) for row in cur.fetchall()]
            
            cur.execute(f"""
                SELECT id FROM topic 
                WHERE subfield_display_name = '{topic2}'
            """)
            topic_id2s = [int(row[0]) for row in cur.fetchall()]
        if not topic_id1s or not topic_id2s:
            return pd.DataFrame(columns=['id', 'title'])
    
    # 2. Neo4j：使用图模式匹配找出同时关联两个主题集合的论文ID
    cypher = """
    MATCH (t1:topic_v)<-[:work_topic_e]-(w:work_v)-[:work_topic_e]->(t2:topic_v)
    WHERE t1.id IN $topic_id1s AND t2.id IN $topic_id2s
    RETURN DISTINCT w.id AS id
    """
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, topic_id1s=topic_id1s, topic_id2s=topic_id2s)
        work_ids = [int(r["id"]) for r in records]
    
    if not work_ids:
        return pd.DataFrame(columns=['id', 'title'])
    
    # 3. PostgreSQL：筛选2022年发表的论文ID
    id_place = ",".join(["%s"] * len(work_ids))
    sql = f"""
    SELECT id FROM work
    WHERE id IN ({id_place}) AND publication_year = 2022
    """
    with ctx.pg_cursor as cur:
        with TimerPhase(timer, "r"):
            cur.execute(sql, work_ids)
            work_ids_2022 = [int(row[0]) for row in cur.fetchall()]
        if not work_ids_2022:
            return pd.DataFrame(columns=['id', 'title'])
    
     # 4. MongoDB：筛选 authorships ≤ 3 的 work_id
    mongo_filter = {
        "_id": {"$in": work_ids_2022},
        "$expr": {
            "$cond": {
                # 条件：检查 doc.authorships 是否真的是数组
                "if": {"$isArray": "$doc.authorships"},
                
                # 如果是数组：检查长度是否 <= 3
                "then": {"$lte": [{"$size": "$doc.authorships"}, 3]},
                
                # 如果不是数组（包括 null 或 missing）：直接返回 False (排除)
                # 这样既不会报错，也不会把 null 混进来
                "else": False
            }
        }
    }
    with TimerPhase(timer, "d"):
        cursor = ctx.mongo_db["work_doc"].find(mongo_filter, {"_id": 1})
        filtered_ids = [int(doc["_id"]) for doc in cursor]
    
    if not filtered_ids:
        return pd.DataFrame(columns=['id', 'title'])
    
    # 5. PostgreSQL：关联work表，按引用数排序取TOP 20
    id_place = ",".join(["%s"] * len(filtered_ids))
    sql = f"""
    SELECT id, title
    FROM work
    WHERE id IN ({id_place})
    ORDER BY cited_by_count DESC, id ASC
    LIMIT 20
    """
    with TimerPhase(timer, "r"):
        result_df = pd.read_sql(sql, ctx._pg_conn, params=filtered_ids)
    
    return result_df

if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = G4(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)