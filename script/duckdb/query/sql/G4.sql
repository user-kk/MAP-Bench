with topic_id1s as(
    select t.id
    from topic t
    where t.subfield_display_name = '__MB_topic1_name__'
),
topic_id2s as(
    select t.id
    from topic t
    where t.subfield_display_name = '__MB_topic2_name__'
),
ids AS (
    select DISTINCT g.wid as id
    from GRAPH_TABLE(
        academic_net
        MATCH (t1: topic_v)<-[e1: work_topic_e]-(w: work_v)-[e2: work_topic_e]->(t2: topic_v)
        where t1.id IN (SELECT id FROM topic_id1s)
        and t2.id IN (SELECT id FROM topic_id2s)
        COLUMNS (t1.id as tid1, t2.id as tid2, w.id as wid)
    ) g
)

select w.id AS id, w.title AS title
from ids join work w on ids.id::bigint = w.id
where w.publication_year = 2022 
and (
    SELECT json_array_length(d.doc->'authorships')
    FROM work_doc d
    WHERE d.id = w.id -- 这个地方不用子查询,直接join 会巨慢,他会直接扫 work_doc 全表
) <= 3
ORDER BY w.cited_by_count DESC,w.id ASC
LIMIT 20;