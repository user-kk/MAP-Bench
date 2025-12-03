WITH topic_info AS (
    SELECT t.id,tv.vec
    FROM topic t
        JOIN topic_vec tv ON t.id = tv.id
    WHERE
        t.display_name = 'Chemistry and Applications of Metal-Organic Frameworks'
),
ranked_papers AS (
SELECT 
    (graph_match.work_id_jsonb)::bigint AS id,
    sqrt( (graph_match.edge_score_jsonb #>> '{}')::float / (wv.vec <-> ti.vec) ) AS topic_score
FROM
(
    MATCH (w:work_v)-[e:work_topic_e]->(t:topic_v)
    RETURN w.id AS work_id_jsonb,
    t.id AS topic_id_jsonb,
    e.score AS edge_score_jsonb
) AS graph_match
JOIN
    topic_info ti ON (graph_match.topic_id_jsonb)::bigint = ti.id
JOIN
    work_vec wv ON (graph_match.work_id_jsonb)::bigint = wv.id
ORDER BY
    topic_score DESC,id ASC
LIMIT 10
)
SELECT
w.title,w.cited_by_count,rp.topic_score
FROM
ranked_papers rp
JOIN work w ON w.id = rp.id
ORDER BY rp.topic_score DESC,w.id ASC;