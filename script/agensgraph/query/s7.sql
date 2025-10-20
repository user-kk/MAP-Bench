WITH ai_papers AS (
    SELECT DISTINCT w.id AS work_id
    FROM 
        work w
    JOIN 
        work_doc wd ON w.id = wd.id
    CROSS JOIN
        jsonb_array_elements(wd.doc -> 'topics') AS k 
    JOIN topic t ON (k->>'id')::bigint = t.id
    WHERE 
        w.publication_year BETWEEN 2022 AND 2025
        AND wd.doc->'abstract_inverted_index' ?& array['model','ResNet']
        AND t.subfield_display_name = 'Artificial Intelligence'
),
author_counts AS (
    SELECT 
        (a_doc -> 'author' ->> 'id')::bigint AS author_id,
        COUNT(DISTINCT w.work_id) AS pub_count
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
    ac.pub_count,
    ac.pub_count::FLOAT / a.works_count as ratio
FROM 
    author_counts ac
JOIN 
    author a ON a.id = ac.author_id
where a.works_count != 0 and a.cited_by_count >= 10000
ORDER BY 
    ac.pub_count DESC,
    ratio DESC, 
    ac.author_id ASC
LIMIT 10;