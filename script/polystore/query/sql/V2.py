#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import sys
import time
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.context import Context
from common.timer import MultiDatabaseTimer as MDTimer, TimerPhase
from pymilvus import Collection

def V2(ctx: "Context",
       seed_work_id: int = 4395661325,
       top_k: int = 5,
       timer: Optional[MDTimer] = None) -> pd.DataFrame:
    """
    对于给定的种子论文，先构建上下文池（该论文引用的作品），然后为上下文池中每篇论文
    基于向量相似度推荐 top_k 篇论文（排除上下文池本身）
    输出：context_work_id 和 recommendations（ID数组）
    """
    
    # 1. Neo4j：构建 context_pool（0-1跳引用的作品）
    cypher = """
    MATCH (p1:work_v)-[:work_referenced_work_e*0..1]->(p2:work_v)
    WHERE p1.id = $wid
    RETURN DISTINCT p2.id AS context_work_id
    """
    
    with TimerPhase(timer, "g"):
        records = ctx.neo4j_session.run(cypher, wid=seed_work_id)
        context_pool_ids = [int(r["context_work_id"]) for r in records]
    
    if not context_pool_ids:
        return pd.DataFrame(columns=['work_id', 'recommendations'])
    
    # 2. Milvus：批量获取 context_pool 中所有作品的向量
    work_collection = ctx.get_milvus_collection("work_vec")
    
    with TimerPhase(timer, "v"):
        expr = f"id in {list(context_pool_ids)}"
        context_results = work_collection.query(
            expr=expr,
            output_fields=["id", "vec"]
        )
        context_vectors = {int(r["id"]): r["vec"] for r in context_results}
    
    if not context_vectors:
        return pd.DataFrame(columns=['work_id', 'recommendations'])
    
    # 3. 为每篇上下文作品搜索 top_k 相似作品（排除 context_pool）
    results = []
    exclude_expr = f"id not in {list(context_pool_ids)}"
    
    with TimerPhase(timer, "v"):
        for context_id, context_vec in context_vectors.items():
            hits = work_collection.search(
                data=[context_vec],
                anns_field="vec",
                param={"metric_type": "L2"},
                limit=top_k,
                expr=exclude_expr
            )[0]
            
            rec_ids = [int(h.id) for h in hits]
            results.append({
                'work_id': context_id,
                'recommendations': rec_ids
            })
    
    return pd.DataFrame(results).reset_index(drop=True)


if __name__ == "__main__":
    ctx = Context("127.0.0.1")
    ctx.use("mapl")
    timer = MDTimer()
    
    t0 = time.perf_counter()
    result = V2(ctx, timer=timer)
    t1 = time.perf_counter()
    
    print(result) 
    print(timer.get_times_map())
    print((t1-t0)*1000)