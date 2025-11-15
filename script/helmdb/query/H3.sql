with topic_info as (
    SELECT t.id as id,tv.vec as vec
        from topic t join topic_vec tv on t.id = tv.id
        where t.display_name = 'Chemistry and Applications of Metal-Organic Frameworks'
),
tv_find AS(
    SELECT  w.id as wid,ti.vec as tvec,e.score as sc
    FROM topic_info ti,
         work_topic_gra MATCH (w: work_v)-[e: work_topic_e]->(t: topic_v)
    WHERE ti.id = t.id
),
related AS (
    SELECT tv.wid as id,
           sqrt((tv.sc)::float / (wv.vec <-> tv.tvec)) AS topic_score
    FROM tv_find tv,work_vec wv
    WHERE tv.wid = wv.id
    ORDER BY sqrt((tv.sc)::float / (wv.vec <-> tv.tvec)) DESC,tv.wid ASC
    limit 10
)
SELECT w.title,
       w.cited_by_count,
       r.topic_score      
FROM related r
JOIN work w ON w.id = r.id;