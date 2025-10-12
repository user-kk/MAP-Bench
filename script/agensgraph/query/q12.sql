WITH reachable AS (
    /* 1. 一次性把 0-2 步能到的 work id 拿出来 */
   MATCH (p1:work_v {id: 4394922388})-[r:work_referenced_work_e*0..2]->(p2:work_v)
        RETURN p2.id AS id
)
SELECT p.title,
       json_agg(a.display_name) AS authors,
       p.publication_year AS year,
       p.cited_by_count AS n_citation
FROM reachable        r
JOIN work             p  ON p.id = r.id::bigint
JOIN work_doc         wd ON wd.id = p.id
/* 2. 把 authorship 拆行 → 连 author → 再聚合 */
JOIN LATERAL jsonb_array_elements(wd.doc->'authorships') AS au ON true
JOIN author a ON (au->'author'->>'id')::bigint = a.id
GROUP BY p.id, p.title, p.publication_year, p.cited_by_count
ORDER BY p.cited_by_count DESC, p.id ASC;