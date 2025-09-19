WITH CoAuthors AS (
    SELECT au.*
    FROM author_author_gra MATCH (a: author_v)-[: author_author_e]-(b: author_v),
    author au ON au.id = b.id
    WHERE a.id = 5040670721
)
SELECT a.display_name, a.cited_by_count
FROM CoAuthors ca
JOIN author a ON a.id = ca.coauthor_id
ORDER BY a.cited_by_count DESC
limit 10;

select * 
    from author_author_gra MATCH (a: author_v)-[: author_author_e]-(b: author_v)
    where a.id = 5040670721

SELECT au.*
    FROM author_author_gra MATCH (a: author_v)-[: author_author_e]-(b: author_v),
    author au 
    WHERE a.id = 5040670721 and au.id = b.id