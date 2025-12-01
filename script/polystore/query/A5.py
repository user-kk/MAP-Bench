#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from context import Context

def A5(ctx: "Context", topic_name:str = 'Artificial Intelligence') -> pd.DataFrame:
    """
    返回 TOP 10 AI 高产区作者
    列：['author_id', 'display_name', 'pub_count', 'ratio']
    年份过滤由 PostgreSQL 完成
    """

    # 1. PostgreSQL：先拿 AI 子领域对应的所有 topic id
    with ctx.pg_cursor as cur:
        cur.execute(
            f"SELECT id FROM topic WHERE subfield_display_name = '{topic_name}'"
        )
        ai_topic_ids = [int(row[0]) for row in cur.fetchall()]
        if not ai_topic_ids:
            return pd.DataFrame(columns=["author_id", "display_name", "pub_count", "ratio"])

    # 2. MongoDB：仅过滤主题 + 摘要关键词（不含年份）
    mongo_pipeline = [
        {"$match": {
            "doc.topics.id": {"$in": ai_topic_ids},
            "doc.abstract_inverted_index.model": {"$exists": True},
            "doc.abstract_inverted_index.ResNet": {"$exists": True}
        }},
        {"$project": {"_id": 1}}
    ]
    cursor = ctx.mongo_db["work_doc"].aggregate(mongo_pipeline)
    work_ids = [int(doc["_id"]) for doc in cursor]
    if not work_ids:
        return pd.DataFrame(columns=["author_id", "display_name", "pub_count", "ratio"])
    
    # 3. PostgreSQL：用年份 2022-2025 再过滤
    id_place = ",".join(["%s"] * len(work_ids))
    sql = f"""
    SELECT id
    FROM work
    WHERE id IN ({id_place})
      AND publication_year BETWEEN 2022 AND 2025
    """
    pg_df = pd.read_sql(sql, ctx._pg_conn, params=work_ids)
    qualified_wids = set(pg_df["id"])
    
    
    # 4. MongoDB：拿这些论文的作者列表
    mongo_filter = {"_id": {"$in": pg_df["id"].tolist()}}
    
    proj = {
        "authorships": "$doc.authorships.author.id",
        "_id":1
    } 
    
    cursor = ctx.mongo_db["work_doc"].find(mongo_filter, proj)
    
    
    # 初步作者列表（无年份）
    work2authors = {
        int(doc["_id"]): list(set(int(aid) for aid in doc.get("authorships", [])))
        for doc in cursor
    }
    
    if not work2authors:
        return pd.DataFrame(columns=["author_id", "display_name", "pub_count", "ratio"])

    # 5. 统计作者在合格论文中的产量
    from collections import Counter
    author_pub = Counter(
        aid
        for wid, aids in work2authors.items()
        if wid in qualified_wids
        for aid in aids
    )
    if not author_pub:
        return pd.DataFrame(columns=["author_id", "display_name", "pub_count", "ratio"])

    # 6. PostgreSQL：补齐作者总篇数、显示名、被引量，并计算 ratio
    aids = list(author_pub.keys())
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
    pg_df = pd.read_sql(sql, ctx._pg_conn, params=aids)

    # 7. 合并 & 排序
    out = (
        pg_df.assign(
            pub_count=lambda x: x["author_id"].map(author_pub),
            ratio=lambda x: x["pub_count"] / x["works_count"]
        )
        .sort_values(
            ["pub_count", "ratio", "author_id"],
            ascending=[False, False, True]
        )
        .head(10)
        .reindex(columns=["author_id", "display_name", "pub_count", "ratio"])
        .reset_index(drop=True)
    )
    return out


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(A5(ctx))