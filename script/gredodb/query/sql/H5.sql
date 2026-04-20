-- @a_id, @b_id 是两篇论文ID
WITH PathNodes AS (
SELECT e.endid AS w_id
FROM work_work_gra
MATCH SHORTEST path = (a: work_v)-[e: work_referenced_work_e] * -> (b: work_v)
WHERE a.id = __MB_a_id__
AND b.id = __MB_b_id__
) 
SELECT w.id, w.title,
(
    select json_agg(authorships.author.display_name)
        from work_doc wc unwind jsonb_array_elements(wc.authorships::jsonb)  as authorships 
        where w.id = wc.id

) as authors,
(
     select json_agg(topics.display_name)
        from work_doc wc unwind jsonb_array_elements(wc.topics::jsonb)  as topics 
        where w.id = wc.id
) as topics,
 w.cited_by_count 
FROM PathNodes f
JOIN work w ON w.id = f.w_id join work_vec wv on w.id = wv.id
ORDER BY wv.vec <-> (select vec from topic_vec tv where tv.id = __MB_topic_id__) ASC ,w.cited_by_count DESC,w.id asc
limit 3;