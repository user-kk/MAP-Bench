WITH HotTopic AS (
-- 找到近五年内发文最多的主题
SELECT t.id::bigint as topic_id
FROM work as w join work_doc as wc on w.id = wc.id cross join unnest(json_extract(wc.doc,'$.topics[*].id')) as t(id)
WHERE w.publication_year >= 2020-5
GROUP BY topic_id
ORDER BY count(1) DESC,topic_id asc
LIMIT 1
),
AuthorsInHotTopic AS (
select DISTINCT g.a_id, g.w_id
from HotTopic ht join GRAPH_TABLE(
    academic_net
    MATCH (au: author_v)<-[e1: work_author_e]-(w: work_v)-[e2: work_topic_e]->(t: topic_v)
    where w.publication_year >= 2020 - 5
    COLUMNS (au.id as a_id,w.id as w_id,t.id as t_id)
) g on ht.topic_id = g.t_id 
),
InstCount AS (
SELECT a.institution_id::bigint AS inst_id, COUNT(1) AS paper_cnt
FROM AuthorsInHotTopic aht join author a ON aht.a_id = a.id
WHERE a.institution_id is not NULL
GROUP BY a.institution_id
ORDER BY COUNT(1) DESC,a.institution_id asc
LIMIT 3
) 
SELECT i.display_name AS institution_name, ic.paper_cnt
FROM InstCount ic,
institution i
WHERE i.id = ic.inst_id
ORDER BY ic.paper_cnt DESC,i.id asc;