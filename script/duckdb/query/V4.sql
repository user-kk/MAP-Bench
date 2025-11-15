WITH ids AS (
    -- 第一步：选择 2018-2023 年间，并且包含 "multi-model database" 关键字的论文
    SELECT w.id AS id
    FROM work w
    JOIN work_doc wc ON w.id = wc.id
    WHERE w.publication_year >= 2018 AND w.publication_year <= 2023
      AND (wc.doc->'abstract_inverted_index'->'multi-model') is not null
      AND (wc.doc->'abstract_inverted_index'->'database') is not null
),
ids2 AS (
    -- 第二步：计算与给定论文的主题向量相似度，取出相似度最高的 20 篇论文 不包含自己
    SELECT ids.id,array_distance(p1_vec.vec,(select p2_vec.vec from work_vec p2_vec where p2_vec.id =  4379620227)) as dis
    FROM ids join work_vec p1_vec on ids.id = p1_vec.id
    WHERE  ids.id != 4379620227
    ORDER BY dis ASC,ids.id asc
    LIMIT 20
)
SELECT 
    json_object(
        'title',  p.title,
        'author', json_extract(wc.doc,'$.authorships[*].author.display_name'),
        'publication_date',  p.publication_date,
        'type',  p.type,
        'cited_by_api_url', p.cited_by_api_url,
        'abstract',  wc.doc->>'abstract',
        'language',  p.language,
        'volume',  wc.doc->>'volume',
        'issue',  wc.doc->>'issue',
        'first_page',  wc.doc->>'first_page',
        'last_page',  wc.doc->>'last_page',
        'doi', wc.doi) AS bib
FROM ids2
JOIN work p ON ids2.id = p.id
JOIN work_doc wc ON p.id = wc.id
ORDER BY ids2.dis ASC,ids2.id asc;



