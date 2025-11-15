-- 第一步：获取目标主题 ID 和向量
WITH topic_info AS (
    SELECT t.id AS topic_id, tv.vec AS topic_vec
    FROM topic t
    JOIN topic_vec tv ON t.id = tv.id
    WHERE t.display_name = 'RNA Methylation and Modification in Gene Expression'
    LIMIT 1
),

-- 第二步：获取目标作者 ID（Zupei Liu）
target_author AS (
    SELECT au.id AS author_id
    FROM author au
    WHERE au.display_name = 'Zupei Liu'
    LIMIT 1
),

-- 第三步：使用 duckpgq 查找 2～4 跳候选作者（排除 1 跳和自身）
Potential AS (
    -- 第三步：使用 duckpgq 查找 2～4 跳候选作者（排除 1 跳和自身）
    SELECT DISTINCT cand.id AS cand_id
    FROM GRAPH_TABLE (
        academic_net
        MATCH (me:author_v)-[e:author_author_e]->{2,4}(cand:author_v)
        WHERE me.id = 5042849120 and cand.id != me.id and not (me)-[e]->(cand)
          AND cand.cited_by_count >= 10000
        COLUMNS (cand.id as id)
    ) 
),

-- 第四步：获取这些候选作者在该主题下的作品
CandidateWork AS (
    SELECT
        au.id AS aid,
        wd.id AS wid
    FROM GRAPH_TABLE (
        author_graph
        MATCH (au:author_v)<-[:work_author_e]-(w:work_v)
        WHERE au.id IN (SELECT to_jsonb(cand_id) FROM Potential)
        COLUMNS (au.id, w.id)
    ) t
    JOIN work_doc wd ON t.wid = wd.id
    WHERE wd.doc->'topics' @> jsonb_build_array(
        jsonb_build_object('id', (SELECT topic_id FROM topic_info))
    )
)

-- 第五步：计算每个候选作者作品的平均向量距离
SELECT
    cw.aid AS author_id,
    avg(wv.vec <-> (SELECT topic_vec FROM topic_info)) AS avg_dis
FROM CandidateWork cw
JOIN work_vec wv ON cw.wid = wv.id
GROUP BY cw.aid
ORDER BY avg_dis ASC, cw.aid ASC
LIMIT 3;


///



SELECT DISTINCT id AS cand_id
    FROM GRAPH_TABLE (
        academic_net
        MATCH (me:author_v)-[e2:author_author_e]->{2,4}(cand:author_v)
        WHERE me.id = 5042849120 
          AND cand.id != 5042849120 
          AND cand.id not in (
            SELECT DISTINCT neigh.id AS id
            FROM GRAPH_TABLE (
                academic_net
                MATCH (me:author_v)-[e1:author_author_e]->(neigh:author_v)
                WHERE me.id = 5042849120
                COLUMNS (neigh.id)
            )
          )
          AND cand.cited_by_count >= 10000
        COLUMNS (cand.id)
    )