#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

def A6(ctx: "Context",
       seed_topic_id: int = 10862,
       top_k_topics: int = 5,
       works_per_topic: int = 3,
       timer: Optional[MDTimer] = None) -> pd.DataFrame:
    
    topic_coll = ctx.get_milvus_collection("topic_vec")
    
    with TimerPhase(timer, "v"):
        seed_vec = topic_coll.query(
            expr=f"id == {seed_topic_id}",
            output_fields=["vec"]
        )[0]["vec"]
        
        hits = topic_coll.search(
            data=[seed_vec],
            anns_field="vec",
            param={"metric_type": "L2"},
            limit=top_k_topics,         
        )[0]
        
        near_ids = [int(h.id) for h in hits[:top_k_topics]]
    
    if not near_ids:
        return pd.DataFrame(columns=['topic_name', 'top_papers_json'])

    cypher = """
    UNWIND $tids AS tid
    MATCH (t:topic_v {id: tid})
    WHERE t.works_count > 10000
    MATCH (w:work_v)-[:work_topic_e]->(t)
    WITH tid, w
    ORDER BY w.cited_by_count DESC, w.id ASC
    WITH tid, collect(w.title)[..$limit] as titles
    RETURN tid, titles
    """
    
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, tids=near_ids, limit=works_per_topic)
        tid2titles = {int(r["tid"]): r["titles"] for r in records}

    id_place = ",".join(["%s"] * len(near_ids))
    sql = f"""
    SELECT id, display_name
    FROM topic
    WHERE id IN ({id_place})
    """
    
    with TimerPhase(timer, "r"):
        pg_df = pd.read_sql(sql, ctx._pg_conn, params=near_ids)

    def make_row(row):
        tid = int(row["id"])
        return {
            "topic_name": row["display_name"],
            "top_papers_json": tid2titles.get(tid, [])
        }

    out = pg_df.apply(make_row, axis=1, result_type="expand")
    order = {tid: i for i, tid in enumerate(near_ids)}
    out["ord"] = out["topic_name"].map(
        lambda name: order[pg_df.set_index("display_name").loc[name, "id"]]
    )
    return out.sort_values("ord")[["topic_name", "top_papers_json"]].reset_index(drop=True)


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = A6(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)