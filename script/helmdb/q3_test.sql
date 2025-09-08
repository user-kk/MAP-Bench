WITH HotTopic AS (
-- 找到近五年内发文最多的主题
SELECT t.id as topic_id, COUNT(*) AS total_works
FROM work_topic_gra MATCH (w: work_v)-[: work_topic_e]->(t: topic_v)
WHERE w.publication_year >= 2020 - 5
GROUP BY t.id
ORDER BY COUNT(*) DESC
LIMIT 1
),
PapersInHotTopic AS (
SELECT w.id as work_id
FROM work_topic_gra MATCH (w: work_v)-[: work_topic_e]->(t: topic-v),
HotTopic ht
WHERE t.id = ht.topic_id
AND w.publication_year >= 2020 - 5
),
InstCount AS (
SELECT a.institution_id::bigint AS inst_id, COUNT(*) AS paper_cnt
FROM PapersInHotTopic pht,work_author_graph MATCH (au: author_v)<-[: work_author_e]-(w: work_v),
author a
WHERE w.id = pht.work_id
AND a.id = au.id
GROUP BY a.institution_id
ORDER BY COUNT(*) DESC
LIMIT 3
) 
SELECT i.display_name AS institution_name, ic.paper_cnt
FROM InstCount ic,
institution i
WHERE i.id = ic.inst_id
ORDER BY ic.paper_cnt DESC;