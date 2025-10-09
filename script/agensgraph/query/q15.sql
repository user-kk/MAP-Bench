-- q15修改如下：
-- 寻找贡献度最大的跨学科领域论文
-- 首先查找所有跨学科论文，然后在引用网络中获得近几年引用过该论文的论文数记为贡献度，按贡献度对跨学科论文排序
SET graph_path = academic_net;
MATCH (a: work_v)-[: work_referenced_work_e]->(b: work_v)
where b.id in (
    SELECT to_jsonb(wc.id)
    FROM work_doc wc
    WHERE wc.doc->'topics' @> '[{"display_name":"Economic Implications of Climate Change Policies"}]'
    AND wc.doc->'topics' @> '[{"display_name":"Economic Impact of Environmental Policies and Resources"}]'
) and a.publication_year >= 2020 and a.type = 'article'
WITH b.id AS id,count(a.id) as cnt
order by cnt desc,id asc
limit 5
return id,cnt