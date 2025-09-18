WITH TopAuthors AS (
    SELECT pr.node_id AS author_id
    FROM cpu_pagerank('author_author_gra'::regclass::bigint, 20, 0.85) 
         AS pr(node_id, pagerank_score)
    ORDER BY pagerank_score DESC
    LIMIT 50
),
TopPapers AS (
    SELECT pr.node_id AS paper_id
    FROM cpu_pagerank('work_work_gra'::regclass::bigint, 20, 0.85) 
         AS pr(node_id, pagerank_score)
    ORDER BY pagerank_score DESC
    LIMIT 50
)
SELECT DISTINCT 
    ta.author_id
FROM 
    TopPapers tp
JOIN 
    work_doc wd ON tp.paper_id = wd.id,
    -- 将 authorships 数组展开成多行
    jsonb_array_elements(wd.doc->'authorships') AS author_obj
JOIN 
    TopAuthors ta ON (author_obj->'author'->>'id')::bigint = ta.author_id;