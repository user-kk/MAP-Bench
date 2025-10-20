WITH HamburgAuthorIDs AS (
    SELECT a.id
    FROM institution i
    JOIN author a ON i.id = a.institution_id
    WHERE i.display_name = 'Universität Hamburg'
),
TopicPaperPairs AS (
    SELECT 
        (work_id_jsonb)::bigint AS work_id,
        (topic_id_jsonb)::bigint AS topic_id,
        topic_name_jsonb #>> '{}' AS display_name
    FROM (
        MATCH (a:author_v)<-[:work_author_e]-(w:work_v)-[:work_topic_e]->(t:topic_v)
        where a.id in (SELECT to_jsonb(id) FROM HamburgAuthorIDs)
        RETURN a.id AS author_id_jsonb,
               w.id AS work_id_jsonb,
               t.id AS topic_id_jsonb,
               t.display_name AS topic_name_jsonb
    ) AS t
)
SELECT 
    topic_id, 
    display_name, 
    COUNT(DISTINCT work_id) AS paper_count
FROM 
    TopicPaperPairs
GROUP BY 
    topic_id, display_name
ORDER BY 
    paper_count DESC, topic_id ASC
LIMIT 10;