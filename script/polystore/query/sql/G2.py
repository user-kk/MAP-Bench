#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context

def G2(ctx: "Context",
       a_id: int = 4377013841,
       b_id: int = 3155434940) -> pd.DataFrame:
    """
    返回两论文最短路径上中间论文的 ['id', 'title']
    按 influence_score = paper_cites + avg(author_cites) 降序，id 升序
    """

    # 1. Neo4j：最短路径节点（不含起点/终点）
    cypher = """
    MATCH sp = shortestPath(
        (p1:work_v {id: $a_id})-[:work_referenced_work_e*]->(p2:work_v {id: $b_id})
    )
    WITH nodes(sp) AS nds
    UNWIND nds AS mid
    WITH mid
    WHERE mid.id <> $a_id AND mid.id <> $b_id
    RETURN mid.id AS p_id
    """
    records = ctx.neo4j_session.run(cypher, a_id=a_id, b_id=b_id)
    path_ids = [int(r["p_id"]) for r in records]
    if not path_ids:
        return pd.DataFrame(columns=["id", "title"])

    # 2. PostgreSQL：先把 work 基本信息 & 被引量拿出来
    id_place = ",".join(["%s"] * len(path_ids))
    sql = f"""
    SELECT id, title, cited_by_count AS paper_cites
    FROM work
    WHERE id IN ({id_place})
    """
    pg_df = pd.read_sql(sql, ctx._pg_conn, params=path_ids)

    # 3. MongoDB：一次性取 authorships → 算作者平均被引
    mongo_filter = {"_id": {"$in": pg_df["id"].tolist()}}
    proj = {"authorships": "$doc.authorships.author.id"}  # 只拿作者 id 列表
    cursor = ctx.mongo_db["work_doc"].find(mongo_filter, proj)

    # 作者 id → 被引量 字典（一次查完）
    author_ids = {int(aid) for doc in cursor for aid in doc.get("authorships", [])}
    if author_ids:
        a_place = ",".join(["%s"] * len(author_ids))
        author_cites = pd.read_sql(
            f"SELECT id, cited_by_count FROM author WHERE id IN ({a_place})",
            ctx._pg_conn, params=list(author_ids)
        ).set_index("id")["cited_by_count"].to_dict()
    else:
        author_cites = {}


    # 计算 avg_author_cites & influence_score
    def calc_influence(row):
        # 回 MongoDB 拿这篇论文的作者列表
        doc = ctx.mongo_db["work_doc"].find_one(
            {"_id": row["id"]},
            {"doc.authorships": 1}
        ) or {}
        a_ids = [
            int(aid)
            for item in (doc.get("doc", {}).get("authorships") or [])
            for aid in [(item.get("author") or {}).get("id")] if aid
        ]
        if not a_ids:
            return row["paper_cites"]
        avg = sum(author_cites.get(aid, 0) for aid in a_ids) / len(a_ids)
        return row["paper_cites"] + avg

    pg_df["influence_score"] = pg_df.apply(calc_influence, axis=1)

    # 4. 排序 & 返回
    return (
        pg_df.sort_values(["influence_score", "id"], ascending=[False, True])
        .reindex(columns=["id", "title"])
        .reset_index(drop=True)
    )


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(G2(ctx))