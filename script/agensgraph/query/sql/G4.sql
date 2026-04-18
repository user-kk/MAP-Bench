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
    MATCH (t1: topic_v)<-[: work_topic_e]-(w: work_v)-[: work_topic_e]->(t2: topic_v)
    where t1.id in (SELECT to_jsonb(id) FROM topic_id1s)
    and t2.id in (SELECT to_jsonb(id) FROM topic_id2s)
    return DISTINCT w.id AS id
)

select w.id AS id, w.title AS title
from ids join work w on ids.id::bigint = w.id join work_doc wc on w.id = wc.id
where w.publication_year = 2022 and jsonb_array_length(wc.doc->'authorships') <= 3
ORDER BY w.cited_by_count DESC,w.id ASC
LIMIT 20;