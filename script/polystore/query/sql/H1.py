#!/usr/bin/env python3

import pandas as pd
import sys
from pathlib import Path
# 把外层目录加入搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context         


def H1(ctx,name:str = "Li Hongbo"):
    """
    参数
    ----
    ctx : Context   已切库的统一上下文实例

    返回
    ----
    pd.DataFrame
        columns: ['id', 'author_name', 'titles', 'paper_cnt']
    """
    # 1. MongoDB：json_contains 过滤
    filter_ = {"doc.display_name_alternatives": name}
    ids = list(ctx.mongo_db.author_doc.distinct("_id", filter_))
    if not ids:
        return pd.DataFrame(columns=['id', 'author_name', 'titles', 'paper_cnt'])

    # 2. PostgreSQL：id -> display_name
    id_place = ",".join(["%s"] * len(ids))
    sql = f"SELECT id, display_name FROM author WHERE id IN ({id_place})"
    pg_df = pd.read_sql(sql, ctx._pg_conn, params=ids)   # 仅改连接对象

    # 3. Neo4j：按 id 聚合论文标题
    cypher = """
    UNWIND $id_list AS uid
    MATCH (au:author_v {id: uid})<-[:work_author_e]-(w:work_v)
    WITH au.id AS id, collect(DISTINCT w.title) AS titles
    RETURN id, titles
    ORDER BY id
    """
    neo_records = ctx.neo4j_session.run(cypher, id_list=ids)
    neo_df = pd.DataFrame([
        {"id": r["id"], "titles": r["titles"], "paper_cnt": len(r["titles"])}
        for r in neo_records
    ])

    # 4. 汇总
    out = (
        pg_df
        .merge(neo_df, on="id", how="inner")
        .rename(columns={"display_name": "author_name"})
        [["id", "author_name", "titles", "paper_cnt"]]
    )
    return out


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1") 
    ctx.use("openalex_middle")
    df = H1(ctx)
    print(df)