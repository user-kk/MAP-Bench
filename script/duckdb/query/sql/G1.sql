-- 第一步：获取目标主题 ID 和向量
WITH topic_info AS (
    SELECT t.id AS topic_id, tv.vec AS topic_vec
    FROM topic t
    JOIN topic_vec tv ON t.id = tv.id
    WHERE t.display_name = '__MB_topic_name__'
    LIMIT 1
),

-- 第二步：获取目标作者 ID（__MB_author_name__）
target_author AS (
    SELECT au.id AS author_id
    FROM author au
    WHERE au.display_name = '__MB_author_name__'
    LIMIT 1
),

-- 第三步：使用 duckpgq 查找 2～4 跳候选作者（排除 1 跳和自身）
Potential AS (
    -- 第三步：使用 duckpgq 查找 2～4 跳候选作者（排除 1 跳和自身）
    SELECT DISTINCT g.id AS cand_id
    FROM GRAPH_TABLE (
        academic_net
        MATCH (me:author_v)-[e:author_author_e]->{2,4}(cand:author_v)
        WHERE me.id = __MB_target_author_id__ and cand.id != me.id
          AND cand.cited_by_count >= 10000
        COLUMNS (cand.id as id)
    ) g
),

-- 第四步：获取这些候选作者在该主题下的作品
CandidateWork AS (
    SELECT
        t.aid AS aid,
        wd.id AS wid
    FROM GRAPH_TABLE (
        academic_net
        MATCH (au:author_v)<-[e:work_author_e]-(w:work_v)
        WHERE au.id IN (SELECT cand_id FROM Potential)
        COLUMNS (au.id as aid, w.id as wid)
    ) t
    JOIN work_doc wd ON t.wid = wd.id
    WHERE json_contains(wd.doc.topics,json_object('id',(SELECT topic_id FROM topic_info limit 1)))
)

-- 第五步：计算每个候选作者的得分，并返回排名前三的作者
SELECT
    cw.aid AS author_id,
    SUM(1.0 / (1.0 + array_distance(wv.vec, (SELECT topic_vec FROM topic_info)))) AS relevance_score
FROM CandidateWork cw
JOIN work_vec wv ON cw.wid = wv.id
GROUP BY cw.aid
ORDER BY relevance_score DESC, cw.aid ASC
LIMIT 3;