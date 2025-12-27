with ids as(
    (
        select distinct w.id
        from topic tc, work_topic_gra MATCH (w: work_v)-[: work_topic_e]->(t: topic_v)
        where tc.subfield_display_name = 'Education' and tc.id = t.id
    )
    intersect (
        select distinct w.id
        from topic tc, work_topic_gra MATCH (w: work_v)-[: work_topic_e]->(t: topic_v)
        where tc.subfield_display_name = 'Computer Vision and Pattern Recognition' and tc.id = t.id
    )
    
)

select w.id AS id, w.title AS title
from ids join work w on ids.id::bigint = w.id join work_doc wc on w.id = wc.id
where w.publication_year = 2022 and jsonb_array_length(wc.doc->'authorships') <= 3
ORDER BY w.cited_by_count DESC,w.id ASC
LIMIT 20;