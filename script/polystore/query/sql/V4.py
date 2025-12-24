#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys, json, time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase
from pymilvus import Collection


def V4(ctx: "Context",
       seed_work_id: int = 3183282730,
       top_k: int = 20,
       timer: Optional[MDTimer] = None) -> pd.DataFrame:

    # 1. MongoDB：关键词 + 年份范围
    mongo_pipeline = [
        {"$match": {
            "doc.abstract_inverted_index.network": {"$exists": True},
            "doc.abstract_inverted_index.model": {"$exists": True},
            "doc.topics.display_name": "Neural Network Fundamentals and Applications"
        }},
        {"$project": {"_id": 1}}
    ]
    with TimerPhase(timer, "d"):
        cursor = ctx.mongo_db["work_doc"].aggregate(mongo_pipeline)
        keyword_ids = {int(doc["_id"]) for doc in cursor}
    if not keyword_ids:
        return pd.DataFrame(columns=["bib"])

    # 2. PostgreSQL：年份过滤
    with TimerPhase(timer, "r"):
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
    with TimerPhase(timer, "v"):
        work_vec_coll = ctx.get_milvus_collection("work_vec")
        seed_vec = work_vec_coll.query(
            expr=f"id == {seed_work_id}",
            output_fields=["vec"]
        )[0]["vec"]

        hits = work_vec_coll.search(
            data=[seed_vec],
            anns_field="vec",
            param={"metric_type": "L2"},
            limit=len(qualified_ids),
            expr=f"id in {qualified_ids} and id != {seed_work_id}"
        )[0]
        top_ids = [int(h.id) for h in hits[:top_k]]
    if not top_ids:
        return pd.DataFrame(columns=["bib"])

    # 4. PostgreSQL：补齐字段并保持顺序
    with TimerPhase(timer, "r"):
        id_place2 = ",".join(["%s"] * len(top_ids))
        sql_work = f"""
        SELECT id, title, publication_date, type, cited_by_api_url,
               language, doi
        FROM work
        WHERE id IN ({id_place2})
        ORDER BY array_position(ARRAY[{id_place2}], id)
        """
        work_df = pd.read_sql(sql_work, ctx._pg_conn, params=top_ids + top_ids)

    # 5. MongoDB：补齐文档字段
    with TimerPhase(timer, "d"):
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

    # 6. 构建 JSON 列
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


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    timer = MDTimer()
    t0 = time.perf_counter()
    print(V4(ctx, timer=timer))
    t1 = time.perf_counter()
    print(timer.get_times_map())
    print((t1-t0)*1000)