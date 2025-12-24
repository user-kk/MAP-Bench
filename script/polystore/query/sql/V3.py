#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase
from pymilvus import Collection

def V3(ctx: "Context",
       seed_work_id: int = 4321448324,
       top_k: int = 100,
       timer: Optional[MDTimer] = None) -> pd.DataFrame:
    
    # 1. Milvus：向量近邻搜索
    with TimerPhase(timer, "v"):
        work_coll = ctx.get_milvus_collection("work_vec")
        seed_vec = work_coll.query(
            expr=f"id == {seed_work_id}",
            output_fields=["vec"]
        )[0]["vec"]
        
        hits = work_coll.search(
            data=[seed_vec],
            anns_field="vec",
            param={"metric_type": "L2"},
            limit=top_k + 1,
            expr=f"id != {seed_work_id}"
        )[0]
        near_ids = [int(h.id) for h in hits]
    
    if not near_ids:
        return pd.DataFrame(columns=['id', 'title'])

    # 2. PostgreSQL：年份过滤
    with TimerPhase(timer, "r"):
        id_place = ",".join(["%s"] * len(near_ids))
        sql = f"""
        SELECT id, title
        FROM work
        WHERE id IN ({id_place})
          AND publication_year BETWEEN 2018 AND 2023
        """
        pg_df = pd.read_sql(sql, ctx._pg_conn, params=near_ids)

    # 3. MongoDB：abstract_inverted_index 必须同时存在 benchmark & database
    with TimerPhase(timer, "d"):
        mongo_filter = {
            "_id": {"$in": pg_df["id"].tolist()},
            "doc.abstract_inverted_index.benchmark": {"$exists": True},
            "doc.abstract_inverted_index.database": {"$exists": True}
        }
        cursor = ctx.mongo_db["work_doc"].find(mongo_filter, {"_id": 1})
        qualified_ids = {int(doc["_id"]) for doc in cursor}

    # 4. 合并 & 按向量距离排序
    out = (
        pg_df[pg_df["id"].isin(qualified_ids)]
        .copy()
        .assign(dis=lambda x: x["id"].map({int(h.id): h.distance for h in hits}))
        .sort_values("dis")
        [["id", "title"]]
        .reset_index(drop=True)
    )
    return out


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    timer = MDTimer()
    t0 = time.perf_counter()
    print(V3(ctx, timer=timer))
    t1 = time.perf_counter()
    print(timer.get_times_map())
    print((t1-t0)*1000)