#!/usr/bin/env python3

import pandas as pd

import sys
from pathlib import Path
# 把外层目录加入搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from context import Context         

def H2(ctx,author_id: int = 5040670721):
    """
    参数
    ----
    ctx : Context  
    返回
    ----
    pd.DataFrame
        columns: ['author_name', 'cited_by_count', 'institution_name']
    """
    
    # 1. Neo4j：单向查合作者 id（去重）
    cypher = """
    MATCH (a:author_v)-[:author_author_e]->(b:author_v)
    WHERE a.id = $aid
    RETURN DISTINCT b.id AS coauthor_id
    """
    records = ctx.neo4j_session.run(cypher, aid=author_id)
    co_ids = [r["coauthor_id"] for r in records]
    if not co_ids:
        return pd.DataFrame(columns=['author_name', 'cited_by_count', 'institution_name'])

    # 2. PostgreSQL：补齐 co-author 信息
    id_place = ",".join(["%s"] * len(co_ids))
    sql = f"""
    SELECT 
           a.display_name AS author_name,
           a.cited_by_count,
           i.display_name AS institution_name
    FROM author a
    JOIN institution i ON a.institution_id = i.id
    WHERE a.id IN ({id_place})
    ORDER BY a.cited_by_count DESC, a.display_name ASC
    LIMIT 10
    """
    df = pd.read_sql(sql, ctx._pg_conn, params=co_ids)   # 仅改连接对象
    return df


# 使用示例
if __name__ == "__main__":
    from context import Context
    ctx = Context("127.0.0.1")
    ctx.use("openalex_middle")
    print(H2(ctx))