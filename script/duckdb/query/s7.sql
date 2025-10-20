WITH ai_papers AS (
    SELECT w.id AS work_id
    FROM 
        work w
    JOIN 
        work_doc wd ON w.id = wd.id
    WHERE 
        w.publication_year BETWEEN 2022 AND 2025
        AND wd.doc.abstract_inverted_index.model is not null
        AND wd.doc.abstract_inverted_index.ResNet is not null
        AND exists (
            select 1
                from unnest(json_extract(wd.doc,'$.topics[*].id')) k join topic t on k.unnest::bigint = t.id
                where t.subfield_display_name = 'Artificial Intelligence' 
        )
),
author_counts AS (
    SELECT 
        a_doc.unnest::bigint AS author_id,
        COUNT(DISTINCT w.work_id) AS pub_count
    FROM 
        ai_papers w
    JOIN 
        work_doc wd ON w.work_id = wd.id
    CROSS JOIN unnest(json_extract(wd.doc,'$.authorships[*].author.id')) a_doc
    GROUP BY 
        author_id
)
SELECT 
    ac.author_id AS author_id,
    a.display_name, 
    ac.pub_count,
    ac.pub_count::FLOAT / a.works_count as ratio
FROM 
    author_counts ac
JOIN 
    author a ON a.id = ac.author_id
where a.works_count != 0 and a.cited_by_count >= 10000
ORDER BY 
    ac.pub_count DESC,
    ratio DESC, 
    ac.author_id ASC
LIMIT 10;