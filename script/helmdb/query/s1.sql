WITH CoAuthors AS (
    SELECT  b.id AS coauthor_id
    FROM author_author_gra MATCH (a: author_v)-[: author_author_e]-(b: author_v),
         author authb
    WHERE b.id = authb.id
      AND a.id = 5040670721
)
SELECT a.display_name, a.cited_by_count
FROM CoAuthors ca
JOIN author a ON a.id = ca.coauthor_id
ORDER BY a.cited_by_count DESC;
#或
WITH CoAuthors AS (
    SELECT b.id AS coauthor_id
    FROM author_author_gra
    MATCH (a: author_v)-[: author_author_e]-(b: author_v)
    WHERE a.id = 5040670721
)
SELECT a.display_name, a.cited_by_count
FROM CoAuthors ca
JOIN author a ON a.id = ca.coauthor_id
ORDER BY a.cited_by_count DESC;