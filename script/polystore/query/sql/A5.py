#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase

def A5(ctx: "Context", topic_name:str = 'Artificial Intelligence', timer: Optional[MDTimer] = None) -> pd.DataFrame:
    """
    返回 TOP 10 AI 高产区作者
    列：['author_id', 'display_name', 'i10_index', 'ratio']
    排序：i10_index DESC, ratio DESC, author_id ASC
    关键词逻辑：包含 'model' 且包含 ('LLM' 或 'transformer')
    """

    # 1. PostgreSQL：先拿 AI 子领域对应的所有 topic id
    with ctx.pg_cursor as cur:
        with TimerPhase(timer, "r"):
            cur.execute(
                "SELECT id FROM topic WHERE subfield_display_name = %s",
                (topic_name,)
            )
            ai_topic_ids = [int(row[0]) for row in cur.fetchall()]
    if not ai_topic_ids:
        return pd.DataFrame(columns=["author_id", "display_name", "i10_index", "ratio"])

    # 2. MongoDB：仅过滤主题 + 摘要关键词
    mongo_pipeline = [
        {"$match": {
            "doc.topics.id": {"$in": ai_topic_ids},
            "$or": [
                {"doc.abstract_inverted_index.LLM": {"$exists": True}},
                {"doc.abstract_inverted_index.transformer": {"$exists": True}}
            ]
        }},
        {"$project": {"_id": 1}}
    ]
    with TimerPhase(timer, "d"):
        cursor = ctx.mongo_db["work_doc"].aggregate(mongo_pipeline)
        work_ids = [int(doc["_id"]) for doc in cursor]
    
    if not work_ids:
        return pd.DataFrame(columns=["author_id", "display_name", "i10_index", "ratio"])
    
    # 3. PostgreSQL：用年份 2022-2025 再过滤，并获取引用数
    id_place = ",".join(["%s"] * len(work_ids))
    sql = f"""
    SELECT id, cited_by_count
    FROM work
    WHERE id IN ({id_place})
      AND publication_year BETWEEN 2022 AND 2025
    """
    with TimerPhase(timer, "r"):
        pg_df = pd.read_sql(sql, ctx._pg_conn, params=work_ids)
    
    # 构建 work_id -> cited_by_count 的映射
    wid_cite_map = dict(zip(pg_df["id"], pg_df["cited_by_count"]))
    
    # 4. MongoDB：拿这些论文的作者列表
    mongo_filter = {"_id": {"$in": pg_df["id"].tolist()}}
    proj = {
        "authorships": "$doc.authorships.author.id",
        "_id": 1
    }
    
    with TimerPhase(timer, "d"):
        cursor = ctx.mongo_db["work_doc"].find(mongo_filter, proj)
        work2authors = {}
        for doc in cursor:
            aids = doc.get("authorships", [])
            if aids:
                valid_aids = [int(aid) for aid in aids if aid is not None]
                work2authors[int(doc["_id"])] = list(set(valid_aids))
    
    if not work2authors:
        return pd.DataFrame(columns=["author_id", "display_name", "i10_index", "ratio"])

    # 5. 统计作者数据
    author_stats = {} # aid -> {'pub': 0, 'i10': 0}

    for wid, aids in work2authors.items():
        if wid not in wid_cite_map:
            continue
            
        cited = wid_cite_map[wid]
        is_i10_paper = 1 if cited >= 10 else 0
        
        for aid in aids:
            if aid not in author_stats:
                author_stats[aid] = {'pub': 0, 'i10': 0}
            
            author_stats[aid]['pub'] += 1
            author_stats[aid]['i10'] += is_i10_paper

    if not author_stats:
        return pd.DataFrame(columns=["author_id", "display_name", "i10_index", "ratio"])

    # 6. PostgreSQL：补齐作者信息
    aids = list(author_stats.keys())
    id_place = ",".join(["%s"] * len(aids))
    sql = f"""
    SELECT id AS author_id,
           display_name,
           works_count,
           cited_by_count
    FROM author
    WHERE id IN ({id_place})
      AND works_count != 0
      AND cited_by_count >= 10000
    """
    with TimerPhase(timer, "r"):
        res_authors = pd.read_sql(sql, ctx._pg_conn, params=aids)

    # 7. 合并 & 排序
    res_authors["pub_count"] = res_authors["author_id"].map(lambda x: author_stats.get(x, {}).get('pub', 0))
    res_authors["i10_index"] = res_authors["author_id"].map(lambda x: author_stats.get(x, {}).get('i10', 0))
    res_authors["ratio"] = res_authors["pub_count"] / res_authors["works_count"]

    out = (
        res_authors
        .sort_values(
            ["i10_index", "ratio", "author_id"],
            ascending=[False, False, True]
        )
        .head(10)
        .reindex(columns=["author_id", "display_name", "i10_index", "ratio"])
        .reset_index(drop=True)
    )
    return out


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("mapl")
    timer = MDTimer()
    t0 = time.perf_counter()
    result = A5(ctx, timer=timer)
    t1 = time.perf_counter()
    print(result)
    print(timer.get_times_map())
    print((t1-t0)*1000)