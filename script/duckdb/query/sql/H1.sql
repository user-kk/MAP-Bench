WITH 
TargetAuthors AS MATERIALIZED (
    SELECT a.id, a.display_name
    FROM author_doc ad
    JOIN author a ON ad.id = a.id
    WHERE json_contains(ad.doc->'display_name_alternatives', '"Li Hongbo"')
),

-- 2. 再通过 GRAPH_TABLE 找出这些作者的论文
AuthorPapers AS (
    SELECT g.id AS author_id, to_json(array_agg(DISTINCT g.title)) AS titles,
           count(DISTINCT g.title) AS paper_cnt
    FROM GRAPH_TABLE (
        academic_net
        MATCH (au:author_v)<-[e:work_author_e]-(w:work_v)
        WHERE au.id IN (SELECT id FROM TargetAuthors) 
        COLUMNS (au.id, w.title)
    ) g
    GROUP BY g.id

)   
SELECT ta.id, ta.display_name AS author_name,
       ap.titles, ap.paper_cnt
FROM TargetAuthors ta
JOIN AuthorPapers ap ON ta.id = ap.author_id
ORDER BY ta.id; 