WITH context_ids_agg AS (

    -- 用下面这个duckdb会直接崩溃
    -- SELECT id AS id
    -- from GRAPH_TABLE (
    --     academic_net
    --     MATCH (p1:work_v)-[e:work_referenced_work_e]->(p2:work_v)
    --     WHERE p1.id = __MB_seed_work_id__
    --     COLUMNS (p2.id AS id)
    -- ) t
    -- UNION
    -- select __MB_seed_work_id__ AS id

    -- 1. 先把所有引用ID聚合成一个数组 (List), 绕开duckpgq的bug

    SELECT list_append(list(id), __MB_seed_work_id__) as all_ids
    FROM GRAPH_TABLE (
        academic_net
        MATCH (p1:work_v)-[e:work_referenced_work_e]->(p2:work_v)
        WHERE p1.id = __MB_seed_work_id__
        COLUMNS (p2.id AS id)
    ) t
),
context_vectors AS (
    -- 2. 获取上下文向量 (需要展开数组再 Join)
    SELECT u.id AS work_id, wv.vec
    FROM context_ids_agg, unnest(all_ids) AS u(id)
    JOIN work_vec wv ON u.id = wv.id
)
-- 3. 核心计算
SELECT 
    cv.work_id,
    ARRAY(
        SELECT w.id
        FROM work_vec w, context_ids_agg cia -- 引用那个聚合数组表
        WHERE NOT list_contains(cia.all_ids, w.id)
        ORDER BY array_distance(w.vec, cv.vec) ASC
        LIMIT 5
    ) as recommendations
FROM context_vectors cv;