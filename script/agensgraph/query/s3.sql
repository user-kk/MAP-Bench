WITH ReferencedPapers AS (
    SELECT
        (work_id_jsonb)::bigint AS ref_work_id,
        (work_title_jsonb) #>> '{}' AS ref_work_title,
        (work_pub_year_jsonb)::integer AS ref_work_publication_year
    FROM (
        MATCH (p1:work_v {id: 4395661325})-[:work_referenced_work_e]->(p2:work_v)
        RETURN p2.id AS work_id_jsonb, 
               p2.title AS work_title_jsonb, 
               p2.publication_year AS work_pub_year_jsonb
    ) AS t
)
SELECT
    r.ref_work_title,
    r.ref_work_publication_year,
    jsonb_agg(a_doc -> 'author') AS authors
FROM
    ReferencedPapers r
JOIN
    work_doc wd ON wd.id = r.ref_work_id,
    jsonb_array_elements(wd.doc -> 'authorships') AS a_doc
GROUP BY
    r.ref_work_id, r.ref_work_title, r.ref_work_publication_year
ORDER BY
    r.ref_work_publication_year DESC, r.ref_work_title ASC
LIMIT 10;