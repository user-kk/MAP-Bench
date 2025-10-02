SET graph_path = academic_net;
WITH PaperIDsInTopic AS (
    SELECT (work_id_jsonb)::bigint AS work_id
    FROM (
        MATCH (w:work_v)-[:work_topic_e]->(t:topic_v)
        WHERE t.display_name = 'Chemistry and Applications of Metal-Organic Frameworks'
        RETURN w.id AS work_id_jsonb
    ) AS t
)
SELECT
    w.title,
    w.cited_by_count,
    w.publication_year,
    w.language
FROM
    PaperIDsInTopic pit
JOIN
    work w ON pit.work_id = w.id
ORDER BY
    w.cited_by_count DESC,
    w.title ASC
LIMIT 10;