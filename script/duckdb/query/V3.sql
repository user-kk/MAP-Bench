WITH gnn_papers AS (
    SELECT id AS work_id
    FROM work_doc
    WHERE doc.abstract_inverted_index.graph is not null
      and doc.abstract_inverted_index.neural is not null
      and doc.abstract_inverted_index.network is not null
)
SELECT
    gp.work_id
FROM
    gnn_papers gp
JOIN
    work_vec p1_vec ON gp.work_id = p1_vec.id
JOIN
    work_vec p2_vec ON p2_vec.id = 4395661325
ORDER BY
    array_distance(p1_vec.vec,p2_vec.vec) ASC,
    gp.work_id ASC
LIMIT 10;