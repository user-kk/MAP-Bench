#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context

def A3(ctx: "Context", institution_name: str = 'Universität Hamburg') -> pd.DataFrame:
    """
    返回指定机构学者发表最多的 TOP 10 主题
    列：['topic_id', 'display_name', 'paper_count']
    步骤：
        1. PG：机构 → 作者 id
        2. Neo4j：作者 → work → topic，内部去重计数并排序
    """

    # 1. PostgreSQL：一条 SQL 拿机构下所有作者 id
    with ctx.pg_cursor as cur:
        cur.execute(
            """
            SELECT a.id
            FROM institution i
            JOIN author a ON i.id = a.institution_id
            WHERE i.display_name = %s
            """,
            (institution_name,)
        )
        author_ids = [int(row[0]) for row in cur.fetchall()]
        if not author_ids:
            return pd.DataFrame(columns=["topic_id", "display_name", "paper_count"])

    # 2. Neo4j：这些作者 → work → topic，内部去重计数并排序
    cypher = f"""
    UNWIND $id_list AS aid
    MATCH (a:author_v {{id: aid}})<-[:work_author_e]-(w:work_v)-[:work_topic_e]->(t:topic_v)
    WITH t.id AS topic_id, max(t.display_name) AS display_name, count(DISTINCT w.id) AS paper_count
    RETURN topic_id, display_name, paper_count
    ORDER BY paper_count DESC, topic_id ASC
    LIMIT 10
    """
    records = ctx.neo4j_session.run(cypher, id_list=author_ids)
    rows = [{"topic_id": int(r["topic_id"]),
             "display_name": r["display_name"],
             "paper_count": int(r["paper_count"])} for r in records]

    return pd.DataFrame(rows, columns=["topic_id", "display_name", "paper_count"])


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(A3(ctx))