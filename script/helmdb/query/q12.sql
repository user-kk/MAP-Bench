SELECT 
    p.title AS title,
    (SELECT json_agg(a.display_name)
        FROM 
            jsonb_array_elements(wd.authorships::jsonb) AS author_obj, 
            author a                                                  
        WHERE 
            (author_obj.author.id)::bigint = a.id             
    ) AS authors, 
    p.publication_year AS year,
    p.cited_by_count AS n_citation
FROM 
    (
        SELECT p2.id AS id
        FROM work_work_gra MATCH (p1: work_v)-[r: work_referenced_work_e]{0,2}->(p2: work_v)
        WHERE p1.id = 4394922388
    ) t1,
    work p,
    work_doc wd
WHERE 
    t1.id = p.id AND p.id = wd.id
ORDER BY 
    p.cited_by_count DESC,p.id asc
