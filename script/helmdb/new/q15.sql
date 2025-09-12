-- q15修改如下：
-- 寻找贡献度最大的跨学科领域论文
-- 首先查找所有跨学科论文，然后在引用网络中获得近几年引用过该论文的论文数记为贡献度，按贡献度对跨学科论文排序
WITH OverlappingPapers AS (
    select wc.id
    from work_doc wc unwind jsonb_array_elements(wc.doc->'topics') as topic
    where topic->>'display_name' in ('Economic Implications of Climate Change Policies','Economic Impact of Environmental Policies and Resources') 
    group by wc.id 
    having count(1) = 2    
)

select p.id, count(a.id) as cnt
from OverlappingPapers p, work_work_gra MATCH (a: work_v)-[: work_referenced_work_e]->(b: work_v)
where p.id = b.id and a.publication_year >= 2020 and a.type = 'article'
GROUP by p.id
order by count(a.id) desc
