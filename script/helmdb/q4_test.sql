-- @a_id, @b_id 是两篇论文ID
WITH PathNodes AS (
SELECT e.endid AS w_id
FROM work_work_gra
MATCH SHORTEST path = (a: work_v)-[e: work_referenced_work_e] * -> (b: work_v)
WHERE a.id = 4395661325
AND b.id = 4321790088
) 
SELECT w.id, w.title, w.cited_by_count
FROM PathNodes f
JOIN work w ON w.id = f.w_id
ORDER BY w.cited_by_count DESC
LIMIT 3;