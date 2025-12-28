#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import math
import sys
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

def G1(ctx: "Context",
       topic_name: str = "RNA Methylation and Modification in Gene Expression",
       seed_author_name: str = "Zupei Liu",
       min_cites: int = 10000,
       top_k: int = 3,
       timer: Optional[MDTimer] = None) -> pd.DataFrame:
    """
    返回 TOP 3 最匹配该主题的 2-4 跳候选作者
    列：['author_id', 'avg_dis']
    全程用图模型拿候选作者及其主题作品
    """

    # 1. PostgreSQL：拿主题 id & 种子作者 id
    with ctx.pg_cursor as cur:
        with TimerPhase(timer, "r"):
            cur.execute(
                "SELECT id FROM topic WHERE display_name = %s LIMIT 1",
                (topic_name,)
            )
            topic_row = cur.fetchone()
        if not topic_row:
            return pd.DataFrame(columns=["author_id", "avg_dis"])
        topic_id = int(topic_row[0])

        with TimerPhase(timer, "r"):
            cur.execute(
                "SELECT id FROM author WHERE display_name = %s LIMIT 1",
                (seed_author_name,)
            )
            auth_row = cur.fetchone()
        if not auth_row:
            return pd.DataFrame(columns=["author_id", "avg_dis"])
        seed_author_id = int(auth_row[0])

    # 2. Milvus：主题向量
    topic_coll = ctx.get_milvus_collection("topic_vec")
    with TimerPhase(timer, "v"):
        topic_vec_rec = topic_coll.query(
            expr=f"id == {topic_id}",
            output_fields=["vec"]
        )
    if not topic_vec_rec:
        return pd.DataFrame(columns=["author_id", "avg_dis"])
    topic_vec = topic_vec_rec[0]["vec"]

    # 3. Neo4j：2-4 跳高被引候选作者 + 这些作者在该主题下的作品
    cypher = """
    MATCH (me:author_v {id: $aid})-[:author_author_e*2..4]->(cand:author_v)
    WHERE cand.cited_by_count >= $min_cites
      AND NOT (me)-[:author_author_e]-(cand)   // 排除 1 跳
    MATCH (cand)<-[:work_author_e]-(w:work_v)-[:work_topic_e]->(t:topic_v {id: $tid})
    RETURN cand.id AS author_id, collect(DISTINCT w.id) AS work_ids
    """
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, aid=seed_author_id, min_cites=min_cites, tid=topic_id)
        author2works = {int(r["author_id"]): list(map(int, r["work_ids"])) for r in records}
    if not author2works:
        return pd.DataFrame(columns=["author_id", "avg_dis"])

    # 4. Milvus：计算每作者平均向量距离
    work_coll = ctx.get_milvus_collection("work_vec")
    rows = []
    for aid, wids in author2works.items():
        if not wids:
            continue
        with TimerPhase(timer, "v"):
            hits = work_coll.search(
                data=[topic_vec],
                anns_field="vec",
                param={"metric_type": "L2"},
                limit=len(wids),
                expr=f"id in {wids}"
            )[0]
            total_score = 0.0
            for h in hits:
                # Milvus L2 metric 返回的是欧氏距离的平方 (Squared Euclidean)
                # 所以真正的 L2 Distance = sqrt(h.distance)
                l2_dist = math.sqrt(h.distance)
                
                # 核心公式应用：
                total_score += 1.0 / (1.0 + l2_dist)
        rows.append({"author_id": aid, "relevance_score": total_score})

    # 5. 排序 & TOP K
    return (
        pd.DataFrame(rows)
        .sort_values(["relevance_score", "author_id"], ascending=[False, True])
        .head(top_k)
        .reset_index(drop=True)
    )


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = G1(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)