SELECT w.title, w.cited_by_count, w.publication_year,w.language
FROM work_topic_gra MATCH (w1: work_v)-[: work_topic_e]->(t: topic_v), work w
WHERE t.properties->>'display_name' = 'Chemistry and Applications of Metal-Organic Frameworks'
AND w1.id = w.id
ORDER BY w.cited_by_count DESC, w.title ASC
LIMIT 10;