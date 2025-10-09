WITH HotTopic AS (
-- 找到近五年内发文最多的主题
SELECT (t->>'id')::bigint as topic_id
FROM work as w , work_doc as wc cross join LATERAL jsonb_array_elements(wc.doc->'topics') as t
WHERE w.publication_year >= 2020-5 and w.id = wc.id
GROUP BY (t->>'id')::bigint
ORDER BY count(1) DESC,(t->>'id')::bigint asc
LIMIT 1
),
PapersInHotTopic AS (
MATCH (au: author_v)<-[: work_author_e]-(w: work_v)-[: work_topic_e]->(t: topic_v)
WHERE t.id = (select to_jsonb(topic_id) from HotTopic) and w.publication_year >= 2020 - 5
return au.id as a_id
),
InstCount AS (
SELECT a.institution_id::bigint AS inst_id, COUNT(1) AS paper_cnt
FROM PapersInHotTopic pht join author a ON pht.a_id::bigint = a.id
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