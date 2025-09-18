WITH CrossDisciplinaryPapers AS (
    SELECT wc.id, wc.doc->'authorships' AS authorships
FROM work w, work_doc wc 
WHERE w.id = wc.id
  AND w.cited_by_count >= 0
  AND w.type = 'article'
  AND w.publication_year >= 2020
  AND wc.doc->'topics' @> '[{"display_name":"Economic Implications of Climate Change Policies"}]'
  AND wc.doc->'topics' @> '[{"display_name":"Economic Impact of Environmental Policies and Resources"}]'
)   
select (author_ship->'author'->>'id')::bigint,count(1) as collaborating_cnt
from  CrossDisciplinaryPapers cp unwind jsonb_array_elements(cp.authorships) as author_ship
group by (author_ship->'author'->>'id')::bigint 
order by count(1) desc,(author_ship->'author'->>'id')::bigint asc
limit 5