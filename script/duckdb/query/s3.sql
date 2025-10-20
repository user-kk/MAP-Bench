SELECT
    r.ref_work_title,
    r.ref_work_publication_year,
    json_extract(wd.doc,'$.authorships[*].author')
FROM
    GRAPH_TABLE (academic_net
        MATCH (p1: work_v)-[e :work_referenced_work_e]->(p2: work_v)
        WHERE  p1.id = 4395661325
        COLUMNS (p2.id AS ref_work_id,p2.title AS ref_work_title,p2.publication_year AS ref_work_publication_year)
    ) r
JOIN
    work_doc wd ON wd.id = r.ref_work_id
ORDER BY
    r.ref_work_publication_year DESC, r.ref_work_title ASC
LIMIT 10;