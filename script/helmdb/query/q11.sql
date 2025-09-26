WITH community AS (
    SELECT *
    FROM cpu_cdlp('author_author_gra'::regclass::bigint, 20) AS t(id,community)
),
TopCommunities AS (
    SELECT community
    FROM community
    GROUP BY community
    ORDER BY COUNT(id) DESC
    LIMIT 3
),
CommunityTopics AS (
    SELECT 
        c.community, 
        wte.endid AS topic_id
    FROM community c
    JOIN work_author_e wae ON c.id = wae.endid
    JOIN work_topic_e wte ON wae.startid = wte.startid
),
TopTopicsPerCommunity AS (
    SELECT 
        community,
        json_agg(topic_display_name) AS top5_topics
    FROM (
        SELECT 
            ct.community, 
            t.properties->>'display_name' AS topic_display_name,
            ROW_NUMBER() OVER (PARTITION BY ct.community ORDER BY COUNT(*) DESC) as rn
        FROM CommunityTopics ct
        JOIN topic_v t ON ct.topic_id = t.id
        GROUP BY ct.community, t.properties->>'display_name'
    ) AS RankedTopics
    WHERE rn <= 5
    GROUP BY community
),
TopAuthorsPerCommunity AS (
    SELECT
        community,
        json_agg(display_name) AS top10_authors
    FROM (
        SELECT 
            c.community,
            a.display_name,
            ROW_NUMBER() OVER (PARTITION BY c.community ORDER BY a.cited_by_count DESC) as rn
        FROM community c
        JOIN author a ON c.id = a.id 
    ) AS RankedAuthors
    WHERE rn <= 10
    GROUP BY community
)
SELECT
    tc.community,
    ttpc.top5_topics,
    tapc.top10_authors
FROM
    TopCommunities tc
LEFT JOIN
    TopTopicsPerCommunity ttpc ON tc.community = ttpc.community
LEFT JOIN
    TopAuthorsPerCommunity tapc ON tc.community = tapc.community;