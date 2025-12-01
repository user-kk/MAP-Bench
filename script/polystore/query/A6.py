#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from context import Context

def A6(ctx: "Context") -> pd.DataFrame:
    """
    返回被引次数最多的 5 篇「双主题」论文
    列：['id', 'cnt']
    """

    # 1. MongoDB：同时包含两个指定主题的论文 id
    mongo_pipeline = [
        {"$match": {
            "doc.topics.display_name": {
                "$all": [
                    "Economic Implications of Climate Change Policies",
                    "Economic Impact of Environmental Policies and Resources"
                ]
            }
        }},
        {"$project": {"_id": 1}}
    ]
    cursor = ctx.mongo_db["work_doc"].aggregate(mongo_pipeline)
    target_ids = [int(doc["_id"]) for doc in cursor]
    if not target_ids:
        return pd.DataFrame(columns=["id", "cnt"])

    # 2. Neo4j：统计 2020+ article 对这些论文的引用次数
    cypher = """
    MATCH (a:work_v)-[:work_referenced_work_e]->(b:work_v)
    WHERE b.id in $ids
      AND a.publication_year >= 2020
      AND a.type = 'article'
    RETURN b.id AS id, count(a.id) AS cnt
    ORDER BY cnt DESC, id ASC
    LIMIT 5
    """
    records = ctx.neo4j_session.run(cypher, ids=target_ids)
    rows = [{"id": int(r["id"]), "cnt": int(r["cnt"])} for r in records]

    return pd.DataFrame(rows, columns=["id", "cnt"])


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(A6(ctx))