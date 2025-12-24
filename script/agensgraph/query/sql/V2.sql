WITH context_pool AS (
    (SELECT id::bigint AS id
    FROM ( -- 不能用[:work_referenced_work_e*0..1] 非常慢
        MATCH (p1:work_v {id: 4395661325})-[:work_referenced_work_e]->(p2:work_v)
        RETURN p2.id
    ) t)
    UNION
    SELECT 4395661325 AS id
),
context_vectors AS (
    -- 第二步：获取这些论文的向量 (Relational Join)
    SELECT cp.id AS work_id, wv.vec
    FROM context_pool cp
    JOIN work_vec wv ON cp.id = wv.id
)
SELECT 
    cv.work_id,
    ARRAY(
        SELECT w.id
        FROM work_vec w
        WHERE w.id not in (select id from context_pool)
        ORDER BY w.vec <-> cv.vec ASC
        LIMIT 5
    ) as recommendations
FROM context_vectors cv;