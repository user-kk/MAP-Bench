WITH OrgAuthors AS (
    SELECT a.id AS author_id
    FROM author a
    JOIN institution i ON a.institution_id = i.id
    WHERE i.display_name = 'Universität Hamburg'
),
AuthorWorks AS (
    SELECT w.id AS work_id
    FROM OrgAuthors oa,
    work_author_gra MATCH (a: author_v)<-[:work_author_e]-(w: work_v)
    WHERE a.id = oa.author_id
),
AuthorTopics AS (
    SELECT t.id AS topic_id,
           t.properties->>'display_name' AS display_name
    FROM AuthorWorks aw,
    work_topic_gra MATCH (w: work_v)-[:work_topic_e]->(t: topic_v)
    WHERE w.id = aw.work_id
)
SELECT topic_id, display_name, COUNT(*) AS paper_count
FROM AuthorTopics at
GROUP BY topic_id, display_name
ORDER BY paper_count DESC
LIMIT 10;