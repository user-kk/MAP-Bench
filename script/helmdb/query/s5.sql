WITH candidate_ids AS (
    SELECT w.id AS work_id
    FROM work w
    JOIN work_doc wd ON w.id = wd.id
    WHERE w.publication_year >= 2020
      AND wd.doc->>'abstract' ILIKE '%climate change%'
),
top_similar AS (
    SELECT c.work_id
    FROM candidate_ids c
    JOIN work_vec v1 ON c.work_id = v1.id
    JOIN topic_vec v2 ON v2.id = 11016
    ORDER BY v1.vec <-> v2.vec ASC
    LIMIT 50
)
SELECT 
    p.id,
    p.title,
    wd.doc->>'abstract' AS abstract
FROM top_similar ts
JOIN work p ON ts.work_id = p.id
JOIN work_doc wd ON wd.id = p.id;