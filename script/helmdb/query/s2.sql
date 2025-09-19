SELECT w1.id, w1.properties->>'title', w1.properties->>'cited_by_count', w1.properties->>'publication_year'
FROM work_topic_gra MATCH (w1: work_v)-[: work_topic_e]->(t: topic_v)
WHERE t.properties->>'display_name' = 'Chemistry and Applications of Metal-Organic Frameworks'
ORDER BY w1.cited_by_count::int DESC, w1.title ASC
LIMIT 10;