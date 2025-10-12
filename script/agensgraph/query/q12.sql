WITH reachable AS (
    /* 1. 一次性把 0-2 步能到的 work id 拿出来 */
   MATCH (p1:work_v {id: 4394922388})-[r:work_referenced_work_e*0..2]->(p2:work_v)
        RETURN p2.id AS id
)
SELECT p.title,
       (
        SELECT json_agg(a.display_name)
        FROM 
            jsonb_array_elements(wd.doc->'authorships') AS author_obj, 
            author a                                                  
        WHERE 
            (author_obj->'author'->>'id')::bigint = a.id   
       ) AS authors,
       p.publication_year AS year,
       p.cited_by_count AS n_citation
FROM reachable        r
JOIN work             p  ON p.id = r.id::bigint
JOIN work_doc         wd ON wd.id = p.id
ORDER BY p.cited_by_count DESC, p.id ASC;