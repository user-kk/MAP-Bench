WITH
TopCitedPaper AS (
    SELECT w.id AS work_id
    FROM work AS w join work_doc AS wd ON w.id = wd.id
    WHERE w.publication_year >= 2023
      AND json_contains(
            json_extract(wd.doc, '$.topics'),
            json_object('display_name', 'Graph Neural Network Models and Applications')
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


PaperVector AS (
    SELECT id, vec
    FROM work_vec
    WHERE id IN (SELECT cited_work_id FROM PaperCitationNetwork)
    UNION ALL
    SELECT id, vec
    FROM work_vec
    WHERE id = (SELECT work_id FROM TopCitedPaper)
),

SimilarityScore AS (
    SELECT pcn.cited_work_id::BIGINT                           AS cited_work_id,
           array_distance(wv1.vec, wv2.vec) AS similarity_score
    FROM PaperCitationNetwork AS pcn
    JOIN PaperVector AS wv1 ON wv1.id = pcn.cited_work_id::BIGINT
    JOIN PaperVector AS wv2 ON wv2.id = (SELECT work_id FROM TopCitedPaper)
    ORDER BY array_distance(wv1.vec, wv2.vec), pcn.cited_work_id
    LIMIT 10
)

SELECT w.title,
       w.cited_by_count,
       ss.similarity_score
FROM SimilarityScore AS ss
JOIN work AS w ON w.id = ss.cited_work_id
ORDER BY ss.similarity_score, ss.cited_work_id;