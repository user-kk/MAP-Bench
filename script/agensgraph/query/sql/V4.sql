WITH ids AS (
    SELECT w.id AS id
    FROM work w
    JOIN work_doc wc ON w.id = wc.id
    WHERE w.publication_year >= 2018 AND w.publication_year <= 2023
      AND wc.doc->'topics' @> '[{"display_name":"__MB_topic_name__"}]' 
      AND wc.doc->'abstract_inverted_index' ?& array['__MB_required_keyword_1__','__MB_required_keyword_2__']
    order by w.cited_by_count desc
),
ids2 AS (
    -- 第二步：计算与给定论文的主题向量相似度，取出相似度最高的 20 篇论文 不包含自己
    SELECT work_vec.id
    FROM work_vec
    WHERE id IN (SELECT id FROM ids) and id != __MB_seed_work_id__
    ORDER BY work_vec.vec <-> (
        select vec from work_vec where id = __MB_seed_work_id__
    ) ASC
    LIMIT 20
)
SELECT 
    jsonb_build_object(
        'author',  (
            jsonb_path_query_array(wc.doc,'$.authorships[*].author.display_name')
        ),
        'title',  p.title,
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
JOIN work_doc wc ON p.id = wc.id;