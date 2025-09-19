SELECT  b.display_name,b.cited_by_count
FROM author_author_gra MATCH (a: author_v)-[: author_author_e]-(b: author_v)
WHERE a.id = 5040670721
ORDER BY b.cited_by_count DESC,b.display_name ASC;