WITH gnn_papers AS (
    SELECT wd.id AS work_id
    FROM work_doc wd
    WHERE doc->'abstract_inverted_index' ?& array['graph','neural','network']
)
SELECT gp.work_id
FROM gnn_papers gp
JOIN work_vec p1_vec ON gp.work_id = p1_vec.id
JOIN work_vec p2_vec ON p2_vec.id = 4395661325
ORDER BY p1_vec.vec <-> p2_vec.vec ASC, gp.work_id ASC
LIMIT 10;