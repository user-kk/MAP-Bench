WITH hamburg_authors AS (
    SELECT a.id 
    FROM institution i
    JOIN author a ON i.id = a.institution_id
    WHERE i.display_name = '__MB_institution_name__'
)
SELECT 
    g.t_id as topic_id,
    max(g.display_name) as display_name,
    count(DISTINCT g.w_id) as paper_count
FROM GRAPH_TABLE (
    academic_net
    MATCH (au:author_v)<-[e1:work_author_e]-(w:work_v)-[e2:work_topic_e]->(t:topic_v)
    -- 核心优化：直接在这里过滤作者 ID
    WHERE au.id IN (SELECT id FROM hamburg_authors)
    COLUMNS (au.id as a_id, t.id as t_id, w.id as w_id, t.display_name)
) g
GROUP BY g.t_id
ORDER BY paper_count DESC, topic_id ASC
LIMIT 10;