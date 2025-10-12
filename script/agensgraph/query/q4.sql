-- @a_id, @b_id 是两篇论文ID
WITH PathNodes AS (
MATCH sp = shortestPath(
        (a:work_v {id: 4395661325})-[:work_referenced_work_e*]->(b:work_v {id: 4316345068})
)
WITH nodes(sp) AS nds
UNWIND nds AS mid
WITH mid
WHERE mid.id <> 4395661325 AND mid.id <> 4316345068
RETURN mid.id AS w_id
) 
SELECT w.id, w.title,
(
    select jsonb_path_query_array(wc.doc,'$.authorships[*].author.display_name')
        from work_doc wc
        where w.id = wc.id

) as authors,
(
     select jsonb_path_query_array(wc.doc,'$.topics[*].display_name')
        from work_doc wc
        where w.id = wc.id
) as topics,
 w.cited_by_count 
FROM PathNodes f
JOIN work w ON w.id = f.w_id::bigint join work_vec wv on w.id = wv.id
ORDER BY wv.vec <-> (select vec from topic_vec tv where tv.id = 10039) ASC ,w.cited_by_count DESC,w.id asc
limit 3;