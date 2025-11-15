WITH candidate_ids AS (
    SELECT w.id AS work_id,w.title AS work_title,wd.doc->>'abstract' AS work_ab
    FROM work w
    JOIN work_doc wd ON w.id = wd.id
    WHERE w.publication_year >= 2020
      AND wd.doc->'abstract_inverted_index' ?& array['climate','change']
)
SELECT c.work_id,c.work_title,c.work_ab AS abstract
FROM candidate_ids c
JOIN work_vec v1 ON c.work_id = v1.id
JOIN topic_vec v2 ON v2.id = 11016
ORDER BY v1.vec <-> v2.vec ASC
LIMIT 10;