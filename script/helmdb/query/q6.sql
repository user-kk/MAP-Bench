WITH ids AS (
    -- 第一步：选择 2018-2023 年间，并且包含 "multi-model database" 关键字的论文
    SELECT w.id AS id
    FROM work w
    JOIN work_doc wc ON w.id = wc.id
    WHERE w.publication_year >= 2018 AND w.publication_year <= 2023
      AND wc.doc->>'abstract' LIKE '%multi-model database%'
),
ids2 AS (
    -- 第二步：计算与给定论文的主题向量相似度，取出相似度最高的 20 篇论文 不包含自己
    SELECT ids.id
    FROM ids, work_vec p1_vec
    WHERE ids.id = p1_vec.id and ids.id != 4379620227
    ORDER BY (p1_vec.vec <-> (
        select p2_vec.vec from work_vec p2_vec where p2_vec.id =  4379620227
    )) ASC,ids.id asc
    LIMIT 20
)
SELECT 
    {
        'author':  (
            SELECT json_agg(a->'author'->>'display_name')
            FROM jsonb_array_elements(wc.doc->'authorships') as a
        ),
        'title':  p.title,
        'publication_date':  p.publication_date,
        'type':  p.type,
        'cited_by_api_url': p.cited_by_api_url,
        'abstract':  wc.doc->>'abstract',
        'language':  p.language,
        'volume':  wc.doc->>'volume',
        'issue':  wc.doc->>'issue',
        'first_page':  wc.doc->>'first_page',
        'last_page':  wc.doc->>'last_page',
        'doi': wc.doi
    } AS bib
FROM ids2
JOIN work p ON ids2.id = p.id
JOIN work_doc wc ON p.id = wc.id;