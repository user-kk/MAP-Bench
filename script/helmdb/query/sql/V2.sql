WITH context_pool AS (
    select p2.id
    from work_work_gra MATCH (p1: work_v)-[: work_referenced_work_e]{0,1}->(p2: work_v)
    where p1.id = 4395661325
),
context_vectors AS (
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