with topic_info as (
    SELECT t.id,tv.vec
        from topic t join topic_vec tv on t.id = tv.id
        where t.display_name = 'Chemistry and Applications of Metal-Organic Frameworks'
),
related AS (
    SELECT w.id,
           sqrt((e.score)::float / (wv.vec <-> ti.vec)) AS topic_score
    FROM topic_info ti, work_topic_gra MATCH (w: work_v)-[e: work_topic_e]->(t: topic_v),work_vec wv
    WHERE ti.id = t.id and w.id = wv.id
    ORDER BY sqrt((e.score)::float / (wv.vec <-> ti.vec)) DESC,w.id ASC
    limit 10
)
SELECT w.title,
       w.cited_by_count,
       r.topic_score      
FROM related r
JOIN work w ON w.id = r.id