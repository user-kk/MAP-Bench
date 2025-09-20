SELECT  authb.display_name,authb.cited_by_count,inst.display_name
FROM author_author_gra MATCH (a: author_v)-[: author_author_e]-(b: author_v),author authb,institution inst
WHERE a.id = 5040670721 AND authb.id = b.id AND authb.institution_id = inst.id
ORDER BY b.cited_by_count DESC,authb.display_name ASC;