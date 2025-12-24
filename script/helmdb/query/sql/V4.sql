WITH ids AS (
    -- 第一步：选择 2018-2023 年间，并且包含 "multi-model database" 关键字的论文
    SELECT w.id AS id
    FROM work w
    JOIN work_doc wc ON w.id = wc.id
    WHERE w.publication_year >= 2018 AND w.publication_year <= 2023
      AND wc.doc->'topics' @> '[{"display_name":"Neural Network Fundamentals and Applications"}]' 
      AND wc.doc->'abstract_inverted_index' ?& array['network','model']
),
ids2 AS (
    -- 第二步：计算与给定论文的主题向量相似度，取出相似度最高的 20 篇论文 不包含自己
    SELECT work_vec.id
    FROM work_vec
    WHERE id IN (SELECT id FROM ids) and id != 3183282730
    ORDER BY work_vec.vec <-> (
        select vec from work_vec where id = 3183282730
    ) ASC
    LIMIT 20
)
SELECT 
    {
        'author':  (
            SELECT json_agg(a.author.display_name)
            FROM jsonb_array_elements(wc.doc.authorships::jsonb) as a
        ),
        'title':  p.title,
        'publication_date':  p.publication_date,
        'type':  p.type,
        'cited_by_api_url': p.cited_by_api_url,
        'abstract':  wc.doc.abstract,
        'language':  p.language,
        'volume':  wc.doc.volume,
        'issue':  wc.doc.issue,
        'first_page':  wc.doc.first_page,
        'last_page':  wc.doc.last_page,
        'doi': wc.doi
    } AS bib
FROM ids2
JOIN work p ON ids2.id = p.id
JOIN work_doc wc ON p.id = wc.id;