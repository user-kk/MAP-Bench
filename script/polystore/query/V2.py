#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from context import Context

def V2(ctx: "Context",
       seed_topic_id: int = 10862,
       top_k_topics: int = 5,
       works_per_topic: int = 3) -> pd.DataFrame:
    """
    返回与 seed_topic_id 向量最接近的 top_k_topics 个主题，
    每个主题取引用数最高的 works_per_topic 篇论文，
    结果列：['topic_name', 'top_papers_json']
    """

    # 1. Milvus：找最近邻的 5 个 topic
    topic_coll = ctx.get_milvus_collection("topic_vec")
    seed_vec = topic_coll.query(
        expr=f"id == {seed_topic_id}",
        output_fields=["vec"]
    )[0]["vec"]

    hits = topic_coll.search(
        data=[seed_vec],
        anns_field="vec",
        param={"metric_type": "L2"},
        limit=top_k_topics,         
    )[0]

    near_ids = [int(h.id) for h in hits[:top_k_topics]]
    print(near_ids)
    if not near_ids:
        return pd.DataFrame(columns=['topic_name', 'top_papers_json'])

    # 2. Neo4j：每个 topic 下引用数最高的 3 篇 work
    cypher = """
    UNWIND $tids AS tid
    MATCH (t:topic_v {id: tid})
    WHERE t.works_count > 10000
    MATCH (w:work_v)-[:work_topic_e]->(t)
    WITH tid, w
    ORDER BY w.cited_by_count DESC, w.id ASC
    WITH tid, collect(w.title)[..$limit] as titles
    RETURN tid, titles
    """
    records = ctx.neo4j_session.run(cypher, tids=near_ids, limit=works_per_topic)

    tid2titles = {int(r["tid"]): r["titles"] for r in records}

    # 3. PostgreSQL：补齐 topic 的 display_name
    id_place = ",".join(["%s"] * len(near_ids))
    sql = f"""
    SELECT id, display_name
    FROM topic
    WHERE id IN ({id_place})
    """
    pg_df = pd.read_sql(sql, ctx._pg_conn, params=near_ids)

    # 4. 拼最终 DataFrame
    def make_row(row):
        tid = int(row["id"])
        return {
            "topic_name": row["display_name"],
            "top_papers_json": tid2titles.get(tid, [])
        }

    out = pg_df.apply(make_row, axis=1, result_type="expand")
    # 按 Milvus 返回顺序（向量距离升序）排列
    order = {tid: i for i, tid in enumerate(near_ids)}
    out["ord"] = out["topic_name"].map(
        lambda name: order[pg_df.set_index("display_name").loc[name, "id"]]
    )
    return out.sort_values("ord")[["topic_name", "top_papers_json"]].reset_index(drop=True)


# 使用示例
if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(V2(ctx))