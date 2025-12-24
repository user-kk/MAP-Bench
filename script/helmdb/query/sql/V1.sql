WITH TopCitedPaper AS (
-- 第一步： 找出近3年内某个领域内被引用量最高的论文 (关系文档join + 文档嵌套结构访问 + 文档包含谓词查询)
SELECT w.id AS work_id
FROM work w, work_doc wc 
WHERE w.publication_year >= 2023
    and w.id = wc.id
    and wc.doc.topics::jsonb @> '[{"display_name":"Graph Neural Network Models and Applications"}]' 
ORDER BY w.cited_by_count DESC,w.id asc
LIMIT 1
),
PaperCitationNetwork AS (
-- 第二步： 找到该论文的引用网络 （图的多跳模式匹配 + 关系图join）
SELECT DISTINCT p2.id AS cited_work_id
FROM TopCitedPaper tcp,
work_work_gra MATCH (p1: work_v)-[: work_referenced_work_e]{1,2}->(p2: work_v)
WHERE p1.id = tcp.work_id
),
SimilarityScore AS (
-- 第三步： 计算论文间的主题向量相似度排名，找相似度最高的前10名（向量ANN搜索）
SELECT id as cited_work_id ,
    vec <-> (SELECT vec FROM work_vec WHERE id = (SELECT work_id FROM TopCitedPaper)) as similarity_score
FROM work_vec 
where id in (SELECT cited_work_id::bigint FROM PaperCitationNetwork)
order by similarity_score asc
limit 10
) 
-- 第四步： 获取前10名论文相关信息，输出最终结果
SELECT w.title, w.cited_by_count, ss.similarity_score
FROM SimilarityScore ss
JOIN work w ON w.id = ss.cited_work_id
ORDER BY ss.similarity_score ASC,ss.cited_work_id ASC


