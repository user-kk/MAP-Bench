WITH ids AS (
    select id,work_vec.vec <-> (select vec from work_vec where id = 4321448324) as dis
    from work_vec 
    order by work_vec.vec <-> (select vec from work_vec where id = 4321448324) asc
    limit 100
)
SELECT wc.id AS id,w.title
FROM ids join work w on ids.id = w.id 
JOIN work_doc wc ON w.id = wc.id
WHERE ids.id != 4321448324 AND w.publication_year >= 2018 AND w.publication_year <= 2023
    AND wc.doc->'abstract_inverted_index' ?& array['benchmark','database']
    AND NOT wc.doc->'abstract_inverted_index' ?| array['survey','review']
order by ids.dis asc