WITH CrossDisciplinaryPapers AS (
    select wc.id, wc.doc->'authorships' as authorships
    from work w, work_doc wc unwind jsonb_array_elements(wc.doc->'topics') as topic
    where w.id = wc.id 
    and w.cited_by_count >= 0
    and w.type = 'article'
    and w.publication_year >= 2020
    and topic->>'display_name' in ('Economic Implications of Climate Change Policies','Economic Impact of Environmental Policies and Resources') 
    group by wc.id ,wc.doc->'authorships'
    having count(1) = 2
)   
select (author_ship->'author'->>'id')::bigint,count(1) as collaborating_cnt
from  CrossDisciplinaryPapers cp unwind jsonb_array_elements(cp.authorships) as author_ship
group by (author_ship->'author'->>'id')::bigint 
order by count(1) desc