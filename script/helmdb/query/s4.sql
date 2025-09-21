WITH Instids AS(
SELECT id AS id
FROM institution
WHERE display_name = 'Universität Hamburg'
),
OrgAuthors AS (
SELECT a.id AS author_id
FROM author a 
JOIN Instids i ON a.institution_id = i.id
),
AuthorWorks AS (
SELECT w.id AS work_id
FROM OrgAuthors oa,
work_author_gra MATCH (a: author_v)<-[:work_author_e]-(w: work_v)
WHERE a.id = oa.author_id
),
AuthorTopics AS (
SELECT t.id AS topic_id,
t.properties->>'display_name' AS display_name,
w.id as work_id
FROM AuthorWorks aw,
work_topic_gra MATCH (w: work_v)-[:work_topic_e]->(t: topic_v)
WHERE w.id = aw.work_id
) 
SELECT topic_id, display_name, COUNT(DISTINCT work_id) AS paper_count
FROM AuthorTopics at
GROUP BY topic_id, display_name
ORDER BY paper_count DESC
LIMIT 10;