WITH ai_papers AS (
    SELECT DISTINCT w.id AS work_id
    FROM 
        work w
    JOIN 
        work_doc wd ON w.id = wd.id,
        jsonb_array_elements(wd.doc -> 'topics') AS t 
    WHERE 
        w.publication_year BETWEEN 2022 AND 2025
        AND wd.doc->'abstract_inverted_index' ?& array['artificial','intelligence']
),
author_counts AS (
    SELECT 
        a_doc -> 'author' ->> 'id' AS author_id_text,
        COUNT(DISTINCT w.work_id) AS pub_count
    FROM 
        ai_papers w
    JOIN 
        work_doc wd ON w.work_id = wd.id,
        jsonb_array_elements(wd.doc -> 'authorships') AS a_doc
    GROUP BY 
        author_id_text
)
SELECT 
    ac.author_id_text AS author_id,
    a.display_name, 
    ac.pub_count
FROM 
    author_counts ac
JOIN 
    author a ON a.id = (ac.author_id_text)::bigint
ORDER BY 
    ac.pub_count DESC, 
    ac.author_id_text ASC
LIMIT 10;