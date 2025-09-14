WITH gnn_papers AS (
    SELECT w.id AS work_id
    FROM work w
    JOIN work_doc wd ON w.id = wd.id
    WHERE wd.doc->>'abstract' ILIKE '%graph neural network%'
)
SELECT gp.work_id
FROM gnn_papers gp
JOIN work_vec p1_vec ON gp.work_id = p1_vec.id
JOIN work_vec p2_vec ON p2_vec.id = 4395661325
ORDER BY p1_vec.vec <-> p2_vec.vec ASC
LIMIT 10;