#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

def H4(ctx: "Context", timer: Optional[MDTimer] = None) -> pd.DataFrame:

    work_id: int = 4395661325

    # 1. Neo4j：图匹配拿被引用论文的基本信息
    cypher = """
    MATCH (w:work_v)-[e:work_referenced_work_e]->(ref:work_v)
    WHERE w.id = $wid
    RETURN ref.id      AS ref_work_id,
           ref.title   AS ref_work_title,
           ref.publication_year AS ref_work_publication_year
    ORDER BY ref.publication_year DESC, ref.title ASC
    LIMIT 10
    """
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, wid=work_id)
        neo_df = (
            pd.DataFrame([dict(r) for r in records])
            .astype({"ref_work_id": int, "ref_work_publication_year": int})
        )
    if neo_df.empty:
        return pd.DataFrame(columns=['ref_work_title',
                                     'ref_work_publication_year',
                                     'authorships_json'])

    ref_ids = neo_df["ref_work_id"].tolist()

    # 2. MongoDB：一次性把 10 篇参考文献的 authorships 字段拉回
    mongo_filter = {"$match": {"_id":{"$in": list(ref_ids)}}}
    mongo_proj = {"$project":{"_id":1,"authors":"$doc.authorships.author"}}
    
    with TimerPhase(timer, "d"):
        cursor = ctx.mongo_db["work_doc"].aggregate([mongo_filter,mongo_proj])
        mongo_df = pd.DataFrame([
            {"ref_work_id": int(doc["_id"]),
             "authorships_json": doc.get("authors")}
            for doc in cursor
        ])

    # 3. 拼 DataFrame
    df = (
        neo_df.merge(mongo_df, on="ref_work_id", how="inner")
              .reindex(columns=["ref_work_title",
                                "ref_work_publication_year",
                                "authorships_json"])
    )
    return df


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("mapl")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = H4(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)