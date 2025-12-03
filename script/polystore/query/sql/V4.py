#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys, json
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context

def V4(ctx: "Context",
       seed_work_id: int = 4379620227,
       top_k: int = 20) -> pd.DataFrame:
    """
    返回与 seed_work_id 最相似的 20 篇论文（2018-2023，含 multi-model+database 关键词），
    结果列：['bib']（每行是一个满足格式的 jsonb 对象）
    """

    # 1. MongoDB：先过滤关键词 + 年份范围
    mongo_pipeline = [
        {"$match": {
            "doc.abstract_inverted_index.multi-model": {"$exists": True},
            "doc.abstract_inverted_index.database": {"$exists": True}
        }},
        {"$project": {"_id": 1}}
    ]
    cursor = ctx.mongo_db["work_doc"].aggregate(mongo_pipeline)
    keyword_ids = {int(doc["_id"]) for doc in cursor}
    if not keyword_ids:
        return pd.DataFrame(columns=["bib"])

    # 2. PostgreSQL：年份过滤
    id_place = ",".join(["%s"] * len(keyword_ids))
    sql = f"""
    SELECT id
    FROM work
    WHERE id IN ({id_place})
      AND publication_year BETWEEN 2018 AND 2023
    """
    pg_df = pd.read_sql(sql, ctx._pg_conn, params=list(keyword_ids))
    qualified_ids = pg_df["id"].tolist()
    if not qualified_ids:
        return pd.DataFrame(columns=["bib"])

    # 3. Milvus：向量近邻搜索（排除自己）
    work_vec_coll = ctx.get_milvus_collection("work_vec")
    seed_vec = work_vec_coll.query(
        expr=f"id == {seed_work_id}",
        output_fields=["vec"]
    )[0]["vec"]

    hits = work_vec_coll.search(
        data=[seed_vec],
        anns_field="vec",
        param={"metric_type": "L2"},
        limit=len(qualified_ids),               # 先拉足够多
        expr=f"id in {qualified_ids} and id != {seed_work_id}"
    )[0]
    if not hits:
        return pd.DataFrame(columns=["bib"])

    top_ids = [int(h.id) for h in hits[:top_k]]     # 取前 20
    if not top_ids:
        return pd.DataFrame(columns=["bib"])

    # 4. PostgreSQL：补齐 work 表字段 + 保持 Milvus 顺序
    id_place2 = ",".join(["%s"] * len(top_ids))
    sql_work = f"""
    SELECT id, title, publication_date, type, cited_by_api_url,
        language, doi
    FROM work
    WHERE id IN ({id_place2})
    ORDER BY array_position(ARRAY[{id_place2}], id)   -- 关键：按 hit 顺序排
    """
    work_df = pd.read_sql(sql_work, ctx._pg_conn, params=top_ids + top_ids)

    # 5. MongoDB：补齐 work_doc 字段
    mongo_filter = {"_id": {"$in": top_ids}}
    proj = {
        "authorships": "$doc.authorships.author.display_name",
        "abstract": "$doc.abstract",
        "volume": "$doc.volume",
        "issue": "$doc.issue",
        "first_page": "$doc.first_page",
        "last_page": "$doc.last_page",
        "doi": "$doi"
    }
    cursor = ctx.mongo_db["work_doc"].find(mongo_filter, proj)
    id2doc = {int(d["_id"]): d for d in cursor}

    # 6. 拼 JSON（与 SQL 的 jsonb_build_object 保持一致）
    def build_json(row):
        wid = int(row["id"])
        doc = id2doc.get(wid, {})
        return {
            "title": row["title"],
            "author": doc.get("authorships", []),
            "publication_date": row["publication_date"],
            "type": row["type"],
            "cited_by_api_url": row["cited_by_api_url"],
            "abstract": doc.get("abstract"),
            "language": row["language"],
            "volume": doc.get("volume"),
            "issue": doc.get("issue"),
            "first_page": doc.get("first_page"),
            "last_page": doc.get("last_page"),
            "doi": row["doi"]
        }

    out = (
        work_df
        .assign(bib=lambda x: x.apply(build_json, axis=1))
        [["bib"]]
        .reset_index(drop=True)
    )
    return out


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(V4(ctx))