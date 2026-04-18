WITH
TopCitedPaper AS MATERIALIZED(
    SELECT w.id AS work_id
    FROM work AS w join work_doc AS wd ON w.id = wd.id
    WHERE w.publication_year >= 2023
      AND json_contains(
            json_extract(wd.doc, '$.topics'),
            json_object('display_name', '__MB_topic_name__')
          )
    ORDER BY w.cited_by_count DESC, w.id
    LIMIT 1
),

PaperCitationNetwork AS (
     select DISTINCT t.cited_work_id
      FROM GRAPH_TABLE (
        academic_net
        MATCH (p1:work_v)-[e:work_referenced_work_e]->{1,2}(p2:work_v)
        WHERE p1.id = (SELECT work_id FROM TopCitedPaper)
        COLUMNS (p2.id AS cited_work_id)
    ) t
),

SimilarityScore AS (
    SELECT id as cited_work_id ,
    array_distance(vec, (SELECT vec FROM work_vec WHERE id = (SELECT work_id FROM TopCitedPaper))) as similarity_score
    FROM work_vec 
    where id in (SELECT cited_work_id FROM PaperCitationNetwork)
    order by similarity_score asc
    limit 10
)

SELECT w.title,
       w.cited_by_count,
       ss.similarity_score
FROM SimilarityScore AS ss
JOIN work AS w ON w.id = ss.cited_work_id
ORDER BY ss.similarity_score, ss.cited_work_id;