#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

def H2(ctx: "Context",
       author_id: int = 5040670721,
       timer: Optional[MDTimer] = None) -> pd.DataFrame:
    
    # 1. Neo4j：单向查合作者 id（去重）
    cypher = """
    MATCH (a:author_v)-[:author_author_e]-(b:author_v)
    WHERE a.id = $aid
    RETURN DISTINCT b.id AS coauthor_id
    """
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, aid=author_id)
        co_ids = [r["coauthor_id"] for r in records]
    
    if not co_ids:
        return pd.DataFrame(columns=['author_name', 'cited_by_count', 'institution_name'])

    # 2. PostgreSQL：补齐 co-author 信息
    id_place = ",".join(["%s"] * len(co_ids))
    sql = f"""
    SELECT 
            a.display_name AS author_name,
            a.cited_by_count,
            i.display_name AS institution_name
    FROM author a
    JOIN institution i ON a.institution_id = i.id
    WHERE a.id IN ({id_place})
    ORDER BY a.cited_by_count DESC, a.display_name ASC
    LIMIT 10
    """

    with TimerPhase(timer, "r"):
        df = pd.read_sql(sql, ctx._pg_conn, params=co_ids)
    
    return df


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = H2(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)