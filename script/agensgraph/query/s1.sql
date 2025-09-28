--helmdb没有无向图的查找，如果一定要无向图需要查两个方向的最并集
--本查询为了方便统一结果只查了一个防线
SET graph_path = academic_net;

WITH CoAuthorIDs AS (
    MATCH (a:author_v)-[:author_author_e]-(b:author_v)
    WHERE a.id = 5040670721
    RETURN DISTINCT b.id AS coauthor_id 
) 
SELECT
    a.display_name,
    a.cited_by_count,
    i.display_name AS institution_name
FROM
    CoAuthorIDs ca
JOIN
    author a ON a.id = ca.coauthor_id
JOIN
    institution i ON a.institution_id = i.id
ORDER BY
    a.cited_by_count DESC, a.display_name ASC
LIMIT 10;