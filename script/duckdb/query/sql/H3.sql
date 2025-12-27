WITH topic_info AS MATERIALIZED(
    SELECT t.id, tv.vec
    FROM topic t
    JOIN topic_vec tv ON t.id = tv.id
    WHERE t.display_name = 'Chemistry and Applications of Metal-Organic Frameworks'
),
related AS (
    SELECT g.w_id as id,
           sqrt((g.score)::float / array_distance(wv.vec, ti.vec)) AS topic_score
    FROM topic_info ti,
         GRAPH_TABLE (academic_net
             MATCH (w:work_v)-[e:work_topic_e]->(t:topic_v)
             where t.id in (SELECT id FROM topic_info)
             COLUMNS (w.id as w_id, e.score as score, t.id as t_id)
         ) g,
         work_vec wv
    WHERE ti.id = g.t_id
      AND g.w_id = wv.id
    ORDER BY topic_score DESC,
             g.w_id ASC
    LIMIT 10
)
SELECT w.title,
       w.cited_by_count,
       r.topic_score
FROM related r
JOIN work w ON w.id = r.id
ORDER BY r.topic_score DESC,w.id ASC;