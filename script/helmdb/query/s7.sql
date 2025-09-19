WITH ai_papers AS (
    SELECT DISTINCT w.id AS work_id
    FROM work w
    JOIN work_doc wd ON w.id = wd.id
    UNWIND json_array_elements((wd.doc->'topics')::json) AS t
    WHERE w.publication_year >= 2022 
      AND w.publication_year <= 2025
      AND wd.doc->>'abstract' ILIKE '%Artificial Intelligence%'
),
author_counts AS (
    SELECT a_doc->'author'->>'id' AS author_id,
           COUNT(DISTINCT w.work_id) AS pub_count
    FROM ai_papers w
    JOIN work_doc wd ON w.work_id = wd.id
    UNWIND json_array_elements((wd.doc->'authorships')::json) AS a_doc
    GROUP BY a_doc->'author'->>'id'
)
SELECT ac.author_id, a.display_name, ac.pub_count
FROM author_counts ac
JOIN author a ON a.id = CAST(ac.author_id AS bigint)
ORDER BY ac.pub_count DESC, ac.author_id ASC
LIMIT 10;