WITH ids AS (
    select id,array_distance(vec,(select vec from work_vec where id = __MB_seed_work_id__))  as dis
    from work_vec 
    order by dis asc
    limit 100
)
SELECT wc.id AS id,w.title
FROM ids join work w on ids.id = w.id 
JOIN work_doc wc ON w.id = wc.id
WHERE ids.id != __MB_seed_work_id__ AND w.publication_year >= 2018 AND w.publication_year <= 2023
    AND (wc.doc->'abstract_inverted_index'->'__MB_required_keyword_1__') is not NULL
    AND (wc.doc->'abstract_inverted_index'->'__MB_required_keyword_2__') is not NULL
    AND (wc.doc->'abstract_inverted_index'->'__MB_excluded_keyword_1__') is NULL
    AND (wc.doc->'abstract_inverted_index'->'__MB_excluded_keyword_2__') is NULL
order by ids.dis asc