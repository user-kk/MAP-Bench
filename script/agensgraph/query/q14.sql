WITH CrossDisciplinaryPapers AS (
SELECT wc.id,
wc.doc -> 'authorships' AS authorships
FROM   work w
JOIN   work_doc wc ON w.id = wc.id
WHERE  w.cited_by_count >= 0
AND  w.type = 'article'
AND  w.publication_year >= 2020
AND  wc.doc -> 'topics' @> '[{"display_name":"Economic Implications of Climate Change Policies"}]'
AND  wc.doc -> 'topics' @> '[{"display_name":"Economic Impact of Environmental Policies and Resources"}]'
)
SELECT (authorship -> 'author' ->> 'id')::bigint  AS author_id,
count(*)                                   AS collaborating_cnt
FROM   CrossDisciplinaryPapers cp
JOIN   LATERAL jsonb_array_elements(cp.authorships) AS authorship ON true
GROUP  BY author_id
ORDER  BY collaborating_cnt DESC, author_id ASC
LIMIT  5;