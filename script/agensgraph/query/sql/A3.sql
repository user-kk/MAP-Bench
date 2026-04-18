WITH AuthorIDs AS (
    SELECT a.id
    FROM institution i
    JOIN author a ON i.id = a.institution_id
    WHERE i.display_name = '__MB_institution_name__'
),
TopicPaperPairs AS (
    SELECT 
        (work_id_jsonb)::bigint AS work_id,
        (topic_id_jsonb)::bigint AS topic_id,
        topic_name_jsonb #>> '{}' AS display_name
    FROM (
        MATCH (a:author_v)<-[:work_author_e]-(w:work_v)-[:work_topic_e]->(t:topic_v)
        where a.id in (SELECT to_jsonb(id) FROM AuthorIDs)
        RETURN a.id AS author_id_jsonb,
               w.id AS work_id_jsonb,
               t.id AS topic_id_jsonb,
               t.display_name AS topic_name_jsonb
    ) AS t
)
SELECT 
    topic_id, 
    max(display_name) as display_name, -- 这样不用把 display_name 加入 GROUP BY
    COUNT(DISTINCT work_id) AS paper_count
FROM 
    TopicPaperPairs
GROUP BY 
    topic_id
ORDER BY 
    paper_count DESC, topic_id ASC
LIMIT 10;