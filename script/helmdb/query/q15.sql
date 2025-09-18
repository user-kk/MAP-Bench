-- q15修改如下：
-- 寻找贡献度最大的跨学科领域论文
-- 首先查找所有跨学科论文，然后在引用网络中获得近几年引用过该论文的论文数记为贡献度，按贡献度对跨学科论文排序
WITH OverlappingPapers AS (
SELECT wc.id
FROM work_doc wc
WHERE doc->'topics' @> '[{"display_name":"Economic Implications of Climate Change Policies"}]'
  AND doc->'topics' @> '[{"display_name":"Economic Impact of Environmental Policies and Resources"}]'
)

select p.id, count(1) as cnt
from OverlappingPapers p, work_work_gra MATCH (a: work_v)-[: work_referenced_work_e]->(b: work_v)
where p.id = b.id and a.publication_year >= 2020 and a.type = 'article'
GROUP by p.id
order by count(1) desc,p.id asc
limit 5
