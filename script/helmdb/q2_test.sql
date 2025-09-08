-- @current_year 表示当前年份
-- @limit_n 表示要获取发文量排名前 N 的机构
--查询描述：获取近五年内发文最多的研究机构，并找出其优先发展的前三个研究领域。可扩展为：获取发文量排名前十的机构，然后针对这些机构在近五年内发文情况，统计最重要/优先的领域排名。
--技术维度：对机构不同领域投入人员、发表文章数量和引用量进行综合排名（连接关系型数据和图型数据，并对其进行过滤）
WITH TopInstitutions AS (
SELECT a.institution_id AS inst_id, COUNT(DISTINCT w.id) AS papers_cnt
FROM work_author_graph 
MATCH (w: work_v)-[: work_author_e]->(au: author_v),author a
WHERE w.publication_year >= 2024 - 5 AND au.id = a.id
GROUP BY a.institution_id
ORDER BY COUNT(DISTINCT w.id) DESC
LIMIT 3
),
InstFields AS (
-- 机构发文映射到各个主题， 并统计出现频次
SELECT ti.inst_id, t.id as topic_id
FROM TopInstitutions ti,
author a,
work_author_graph MATCH (a2: author_v)<-[: work_author_e ]-(w1: work_v),
work_topic_gra MATCH (w2: work_v)-[: work_topic_e]->(t: topic_v)
WHERE a.institution_id = ti.inst_id
AND a2.id = a.id
AND w1.publication_year >= 2024 - 5
AND w1.id = w2.id
) 
SELECT i.display_name AS institution_name, it.topic_id, COUNT(*) AS freq
FROM InstFields it
JOIN institution i ON i.id = it.inst_id
GROUP BY i.display_name, it.topic_id
ORDER BY COUNT(*) DESC
LIMIT 3;