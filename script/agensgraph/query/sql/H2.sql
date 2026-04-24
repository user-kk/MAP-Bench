SELECT
    a.display_name,
    a.cited_by_count,
    i.display_name AS institution_name
FROM
    (
    MATCH (a:author_v)-[:author_author_e]-(b:author_v)
    WHERE a.id = __MB_author_id__
    RETURN b.id AS coauthor_id 
    )  ca
JOIN
    author a ON a.id = ca.coauthor_id::bigint
JOIN
    institution i ON a.institution_id = i.id
ORDER BY
    a.cited_by_count DESC, a.display_name ASC
LIMIT 10;