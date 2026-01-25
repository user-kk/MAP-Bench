WITH HotTopic AS (
-- 找到近五年内发文最多的主题
SELECT t.id::bigint as topic_id
FROM work as w , work_doc as wc unwind jsonb_array_elements(wc.topics::jsonb) as t
WHERE w.publication_year >= 2020-5 and w.id = wc.id
GROUP BY topic_id
ORDER BY count(1) DESC,topic_id asc
LIMIT 1
),
PapersInHotTopic AS (
SELECT w.id as work_id
FROM work_topic_gra MATCH (w: work_v)-[: work_topic_e]->(t: topic_v),
HotTopic ht
WHERE t.id = ht.topic_id 
AND w.publication_year is not NULL
AND w.publication_year >= 2020 - 5
),
InstCount AS (
SELECT a.institution_id::bigint AS inst_id, COUNT(*) AS paper_cnt
FROM PapersInHotTopic pht,work_author_gra MATCH (au: author_v)<-[: work_author_e]-(w: work_v),
author a
WHERE w.id = pht.work_id
AND a.id = au.id
AND a.institution_id is not NULL
GROUP BY a.institution_id
ORDER BY COUNT(*) DESC,a.institution_id asc
LIMIT 3
) 
SELECT i.display_name AS institution_name, ic.paper_cnt
FROM InstCount ic,
institution i
WHERE i.id = ic.inst_id
ORDER BY ic.paper_cnt DESC,i.id asc;