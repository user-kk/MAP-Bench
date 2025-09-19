WITH component AS (
-- 计算作者合作网络中的弱连通分量
SELECT *
FROM cpu_wcc('author_author_gra'::regclass::bigint)
AS component(node_id, component_id)
),
ids AS (
-- 按连通分量的大小排序， 选择前 N 大的连通分量
SELECT component_id AS id
FROM component
GROUP BY component_id
ORDER BY COUNT(node_id) DESC
LIMIT 5
) 
SELECT t.rank, a.display_name
FROM (SELECT id, ROW_NUMBER() OVER () AS rank FROM ids) AS t,
component,
author a
WHERE t.id = component.component_id
AND component.node_id = a.id;