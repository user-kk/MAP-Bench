#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
from typing import Optional
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase


def H3(ctx: "Context", timer: Optional[MDTimer] = None) -> pd.DataFrame:
    topic_name = "Chemistry and Applications of Metal-Organic Frameworks"

    # 1. PG：主题 id
    with ctx.pg_cursor as cur:
        with TimerPhase(timer, "r"):
            cur.execute("SELECT id FROM topic WHERE display_name = %s LIMIT 1", (topic_name,))
            row = cur.fetchone()
    if not row:
        return pd.DataFrame(columns=["title", "cited_by_count", "topic_score"])
    topic_id = row[0] # 10096

    # 2. Milvus：主题向量
    topic_collection = ctx.get_milvus_collection("topic_vec")
    work_collection = ctx.get_milvus_collection("work_vec")
    with TimerPhase(timer, "v"):
        topic_vec_rec = topic_collection.query(
            expr=f"id == {topic_id}",
            output_fields=["vec"]
        )
    if not topic_vec_rec:
        return pd.DataFrame(columns=["title", "cited_by_count", "topic_score"])

    # 3. Neo4j：全量 (work_id, edge_score)
    cypher = """
    MATCH (w:work_v)-[e:work_topic_e]->(t:topic_v)
    WHERE t.id = $tid
    RETURN w.id AS work_id, e.score AS edge_score
    """
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, tid=topic_id)
        work_ids = []
        edge_scores = []
        for r in records:
            work_ids.append(int(r["work_id"]))
            edge_scores.append(float(r["edge_score"]))
    
    if not work_ids:
        return pd.DataFrame(columns=["title", "cited_by_count", "topic_score"])

    # 4. PG：临时表灌入 edge_score
    with ctx.temp_pg_table('tmp_work_score') as cur:
        cur.execute("""
            CREATE TEMP TABLE tmp_work_score AS
            SELECT work_id::bigint, edge_score::float, 0::float AS l2_distance
            FROM unnest(%s::bigint[], %s::float[]) AS t(work_id, edge_score)
        """, (list(work_ids), list(edge_scores)))
        
        cur.execute("""
            create index on tmp_work_score(work_id);
        """)
    
        with TimerPhase(timer, "v"):
            res = work_collection.search(
                    data=[topic_vec_rec[0]["vec"]],
                    anns_field="vec",
                    param={"metric_type": "L2"},
                    limit= min(len(work_ids), 16384),
                    expr=f"id in {list(work_ids)}",
                )[0]


        for hit in res:
            cur.execute("""
                UPDATE tmp_work_score
                SET l2_distance = %s
                WHERE work_id = %s
            """, (hit.distance, int(hit.id)))
        

        # 6. 算分 Top-10
        with TimerPhase(timer, "r"):
            cur.execute("""
                with ids as (
                    SELECT work_id as id,
                        sqrt(edge_score / sqrt(l2_distance)) AS topic_score
                    FROM   tmp_work_score 
                    WHERE  l2_distance > 0
                    ORDER  BY topic_score DESC, work_id ASC
                    LIMIT 10
                )
                SELECT work.title, work.cited_by_count,ids.topic_score
                FROM  work join ids on work.id = ids.id
            """)
            
            df = pd.DataFrame(
                cur.fetchall(),           # 一次性拉取全部结果
                columns=[desc[0] for desc in cur.description]
            )
            return df


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("mapl")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = H3(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)