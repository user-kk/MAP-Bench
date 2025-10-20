WITH refs AS (
    SELECT p2.id AS ref_work_id,p2.title AS ref_work_title,p2.publication_year AS ref_work_publication_year
    FROM work_work_gra MATCH (p1: work_v)-[:work_referenced_work_e]->(p2: work_v)
    WHERE p1.id = 4395661325
)
-- 第二步：对找到的文献进行处理
SELECT
    r.ref_work_title,
    r.ref_work_publication_year,
    json_agg(a_doc->'author') AS authors
FROM
    refs r
JOIN
    work_doc wd ON wd.id = r.ref_work_id,
    jsonb_array_elements(wd.authorships::jsonb) AS a_doc
GROUP BY
    r.ref_work_id, r.ref_work_title, r.ref_work_publication_year
ORDER BY
    r.ref_work_publication_year DESC, r.ref_work_title ASC
LIMIT 10;