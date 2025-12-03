SELECT
    a.display_name,
    a.cited_by_count,
    i.display_name AS institution_name
FROM GRAPH_TABLE (academic_net
        MATCH (a:author_v)-[e:author_author_e]->(b:author_v)
        WHERE a.id = 5040670721
        COLUMNS (b.id AS coauthor_id)
    ) ca
JOIN author       a ON a.id = ca.coauthor_id
JOIN institution  i ON a.institution_id = i.id
ORDER BY a.cited_by_count DESC, a.display_name ASC
LIMIT 10;