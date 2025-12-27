with TopInstitutions( 
    -- 1. 近 5 年发文最多的 3 所机构
    SELECT institution.id::bigint AS inst_id,
           count(1) as papers_cnt
    FROM ( -- duckdb不支持跨UNNEST下推，所以手动下推
            SELECT id
            FROM work
            WHERE publication_year >= 2024-5
    ) w join work_doc wc on w.id = wc.id CROSS join unnest(json_extract(doc,'$.authorships[*].institution.id')) as institution(id) 
    WHERE w.id = wc.id
      AND inst_id is not NULL
    GROUP BY inst_id
    ORDER BY papers_cnt DESC, inst_id ASC
    LIMIT 3
),

-- 2. 这些机构旗下作者近 5 年的论文-主题映射
InstFields AS (
    SELECT a.institution_id  AS inst_id,
           g.topic_id          AS topic_id,
           COUNT(*)                AS freq
    FROM GRAPH_TABLE (
        academic_net
        MATCH (a2:author_v)<-[e1:work_author_e]-(w:work_v)-[e2:work_topic_e]->(t:topic_v)
        WHERE a2.id in (SELECT a.id from TopInstitutions ti join author a on ti.inst_id = a.institution_id) 
            and w.publication_year >= 2024-5
        COLUMNS (a2.id author_id, t.id topic_id)
    ) g join author a ON g.author_id = a.id
    GROUP BY a.institution_id, topic_id
),

-- 3. 每机构取频次最高的 3 个主题
Ranked AS (
    SELECT inst_id,
           topic_id,
           freq,
           row_number() OVER (PARTITION BY inst_id ORDER BY freq DESC, topic_id ASC) AS rank
    FROM InstFields
)


SELECT i.display_name      AS institution_name,
       t.display_name      AS topic,
       r.freq
FROM Ranked r
JOIN institution i ON i.id = r.inst_id
JOIN topic t       ON t.id = r.topic_id
WHERE r.rank <= 3
ORDER BY i.id, r.rank