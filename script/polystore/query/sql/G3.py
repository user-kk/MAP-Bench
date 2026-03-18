#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys, json
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

def G3(ctx: "Context",
       seed_work_id: int = 4394922388,
       timer: Optional[MDTimer] = None) -> pd.DataFrame:
    """
    返回 0-2 步引用网络内所有论文的
    ['title', 'authors', 'year', 'n_citation']
    按 cited_by_count 降序，id 升序
    """

    # 1. Neo4j：0-2 步可达节点（含自己）
    cypher = """
    MATCH (p1:work_v {id: $wid})-[*0..4]->(p2:work_v)
    RETURN DISTINCT p2.id AS id
    """
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, wid=seed_work_id)
        reachable_ids = [int(r["id"]) for r in records]
    
    if not reachable_ids:
        return pd.DataFrame(columns=["title", "authors", "year", "n_citation"])

    # 2. PostgreSQL：补齐 work 字段
    id_place = ",".join(["%s"] * len(reachable_ids))
    sql = f"""
    SELECT id, title, publication_year AS year, cited_by_count AS n_citation
    FROM work
    WHERE id IN ({id_place})
    ORDER BY cited_by_count DESC, id ASC
    """
    with TimerPhase(timer, "r"):
        pg_df = pd.read_sql(sql, ctx._pg_conn, params=reachable_ids)

    # 3. MongoDB：一次性拿 authorships
    mongo_filter = {"_id": {"$in": pg_df["id"].tolist()}}
    proj = {
        "authorships": "$doc.authorships.author.display_name"
    }
    with TimerPhase(timer, "d"):
        cursor = ctx.mongo_db["work_doc"].find(mongo_filter, proj)
        id2authors = {int(d["_id"]): d.get("authorships", []) for d in cursor}

    # 4. 拼结果
    out = (
        pg_df.assign(authors=lambda x: x["id"].map(id2authors))
             .reindex(columns=["title", "authors", "year", "n_citation"])
             .reset_index(drop=True)
    )
    return out


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("mapl")
    timer = MDTimer()
    t0 = time.perf_counter()
    df = G3(ctx, timer=timer)
    t1 = time.perf_counter()
    print(df)
    print(timer.get_times_map())
    print((t1-t0)*1000)