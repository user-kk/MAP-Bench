WITH refs AS (
    SELECT p2.id AS ref_work_id
    FROM work_work_gra MATCH (p1: work_v)-[: work_referenced_work_e]->(p2: work_v)
    WHERE p1.id = 4395661325
)
SELECT w.title,
       w.publication_year,
       a_doc->'author'->>'id'   AS author_id,
       a_doc->'author'->>'display_name' AS author_name
FROM refs r
JOIN work w ON w.id = r.ref_work_id
JOIN work_doc wd ON wd.id = r.ref_work_id
UNWIND json_array_elements((wd.doc->'authorships')::json) AS a_doc
ORDER BY w.publication_year DESC
LIMIT 10;