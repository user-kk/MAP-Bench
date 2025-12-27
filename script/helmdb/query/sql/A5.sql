WITH ai_topic_ids AS (
    SELECT id FROM topic WHERE subfield_display_name = 'Artificial Intelligence'
),
ai_papers AS (
    SELECT w.id AS work_id, w.cited_by_count 
    FROM work w
    JOIN work_doc wd ON w.id = wd.id
    WHERE 
        w.publication_year BETWEEN 2022 AND 2025
        AND wd.doc->'abstract_inverted_index' ?| array['LLM','transformer']
        AND EXISTS (
            SELECT 1 
            FROM jsonb_array_elements(wd.doc -> 'topics') t
            WHERE (t->>'id')::bigint IN (SELECT id FROM ai_topic_ids)
        )
),
author_counts AS (
    SELECT 
        (a_doc -> 'author' ->> 'id')::bigint AS author_id,
        COUNT(DISTINCT w.work_id) AS pub_count,
        COUNT(DISTINCT CASE WHEN w.cited_by_count >= 10 THEN w.work_id END) AS i10_index
    FROM 
        ai_papers w
    JOIN 
        work_doc wd ON w.work_id = wd.id,
        jsonb_array_elements(wd.doc -> 'authorships') AS a_doc
    GROUP BY 
        author_id
)
SELECT 
    ac.author_id AS author_id,
    a.display_name, 
    ac.i10_index,
    ac.pub_count::FLOAT / a.works_count as ratio
FROM 
    author_counts ac
JOIN 
    author a ON a.id = ac.author_id
where a.works_count != 0 and a.cited_by_count >= 10000
ORDER BY 
    ac.i10_index DESC,
    ratio DESC, 
    ac.author_id ASC
LIMIT 10;