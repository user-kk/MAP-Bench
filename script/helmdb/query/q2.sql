-- @current_year 表示当前年份
-- @limit_n 表示要获取发文量排名前 N 的机构
--查询描述：获取近五年内发文最多的研究机构，并找出其优先发展的前三个研究领域。可扩展为：获取发文量排名前十的机构，然后针对这些机构在近五年内发文情况，统计最重要/优先的领域排名。
--技术维度：对机构不同领域投入人员、发表文章数量和引用量进行综合排名（连接关系型数据和图型数据，并对其进行过滤）
WITH TopInstitutions AS (

select (author_ship->'institution'->>'id')::float::bigint as inst_id,COUNT(w.id) as papers_cnt
from work w,work_doc wc unwind jsonb_array_elements(wc.doc->'authorships') as author_ship
where w.id = wc.id and w.publication_year >= 2024-5 and author_ship->'institution'->>'id' != 'nan'
GROUP by (author_ship->'institution'->>'id')::float::bigint
order by COUNT(w.id) DESC, (author_ship->'institution'->>'id')::float::bigint ASC
limit 3

),
InstFields AS (
-- 机构发文映射到各个主题， 并统计出现频次
SELECT a.institution_id as inst_id, t.id as topic_id,count(1) as freq
FROM TopInstitutions ti,
author a,
work_author_gra MATCH (a2: author_v)<-[: work_author_e ]-(w1: work_v),
work_topic_gra MATCH (w2: work_v)-[: work_topic_e]->(t: topic_v)
WHERE ti.inst_id = a.institution_id AND a.id = a2.id
AND w1.publication_year >= 2024 - 5
AND w1.id = w2.id
GROUP by a.institution_id, t.id
)

SELECT i.display_name AS institution_name, t.display_name as topic, k.freq as freq
FROM (
    select inf.inst_id,inf.topic_id,inf.freq,row_number() over (PARTITION BY inf.inst_id ORDER BY inf.freq DESC,inf.inst_id) as rank
        from InstFields inf
) k
JOIN institution i ON i.id = k.inst_id
JOIN topic t on t.id = k.topic_id
WHERE k.rank <=3