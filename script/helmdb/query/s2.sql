WITH Coworkid AS(
	SELECT w1.id AS work_id
	FROM work_topic_gra MATCH (w1: work_v)-[: work_topic_e]->(t: topic_v)
	WHERE t.properties->>'display_name' = 'Chemistry and Applications of Metal-Organic Frameworks'
)
SELECT w.title, w.cited_by_count, w.publication_year,w.language
FROM Coworkid w1, work w
WHERE w1.work_id = w.id
ORDER BY w.cited_by_count DESC, w.title ASC
LIMIT 10;