WITH PathNodes AS (
 select work_v.id as w_id
    from GRAPH_TABLE(
        academic_net
        MATCH p = ANY SHORTEST (p1:work_v where p1.id = __MB_a_id__)-[e:work_referenced_work_e]->*(p2:work_v where p2.id = __MB_b_id__)
        COLUMNS (vertices(p) as node_ids)
    ) g cross join unnest(g.node_ids) as n(rowid) join work_v on n.rowid = work_v.rowid
    where work_v.id <> __MB_a_id__ and work_v.id <> __MB_b_id__
) 
SELECT w.id, w.title,
(
    select json_extract(wc.doc,'$.authorships[*].author.display_name')
        from work_doc wc
        where w.id = wc.id

) as authors,
(
     select json_extract(wc.doc,'$.topics[*].display_name')
        from work_doc wc
        where w.id = wc.id
) as topics,
 w.cited_by_count 
FROM PathNodes f
JOIN work w ON w.id = f.w_id::bigint join work_vec wv on w.id = wv.id
ORDER BY array_distance(wv.vec,(select vec from topic_vec tv where tv.id = __MB_topic_id__)) ASC ,w.cited_by_count DESC,w.id asc
limit 3;