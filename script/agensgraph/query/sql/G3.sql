WITH reachable AS (
   MATCH (p1:work_v {id: 4399669303})-[r:work_referenced_work_e*0..2]->(p2:work_v)
   RETURN DISTINCT p2.id AS id
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
WHERE p.cited_by_count > 100
ORDER BY p.cited_by_count DESC, p.id ASC;