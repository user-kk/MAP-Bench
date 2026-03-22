#!/usr/bin/env python3
import json, time, os, random
import pandas as pd
from pathlib import Path
import sys
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

# --------- 主逻辑 ---------
def A2(ctx: "Context", author_id: int = 5015704722, timer: Optional[MDTimer] = None) -> pd.DataFrame:
    """
    返回目标作者每年合作次数最多的前 3 位合作者
    列：['year', 'top3_id']
    全程 MongoDB 内完成拆年、计数、排名
    """

    # 1. Neo4j：先把合作关系列表拉回来（JSON 字符串）
    cypher = """
    MATCH (a:author_v {id: $aid})-[e:author_author_e]->(b:author_v)
    RETURN b.id AS id, e.list AS list
    """
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, aid=author_id)
        rows = [{"_id": int(r["id"]), "list": json.loads(r["list"])} for r in records]
    
    if not rows:
        return pd.DataFrame(columns=["year", "top3_id"])

    # 2. 写入临时集合，list 已是数组
    with ctx.temp_mongo_collection() as tmp:
        tmp.insert_many(rows)

        # 3. MongoDB 内：拆年 → 计数 → 排名 → 每年 TOP3
        pipeline = [
            {"$unwind": "$list"},
            {"$replaceRoot": {"newRoot": {"coId": "$_id", "year": {"$toInt": "$list.year"}}}},
            {"$group": {"_id": {"year": "$year", "coId": "$coId"}, "cnt": {"$sum": 1}}},
            {"$sort": {"_id.year": 1, "cnt": -1, "_id.coId": 1}},   # 先次数，后id
            {"$group": {
                "_id": "$_id.year",
                "items": {"$push": {"coId": "$_id.coId", "cnt": "$cnt"}}
            }},
            {"$project": {
                "year": "$_id",
                "top3_id": {"$slice": ["$items.coId", 3]}   # 只取前 3 个 id
            }}
        ]
        with TimerPhase(timer, "d"):
            cursor = tmp.aggregate(pipeline, allowDiskUse=True)
            df = pd.DataFrame(list(cursor))

    return df.reindex(columns=["year", "top3_id"]).reset_index(drop=True)


# --------- 入口 ---------
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("mapl")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = A2(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)