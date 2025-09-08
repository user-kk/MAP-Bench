WITH TopCitedPaper AS (
-- 第一步： 找出近五年内被引用量最高的论文（ Top 1）
SELECT w.id AS work_id
FROM work w
WHERE w.publication_year >= 2020 - 5
ORDER BY w.cited_by_count DESC
LIMIT 1
),
PaperCitationNetwork AS (
-- 第二步： 找到该论文的引用网络（ 2 跳以内的引用关系）
SELECT p2.id AS cited_work_id
FROM TopCitedPaper tcp,
work_work_gra MATCH (p1: work_v)-[: work_referenced_work_e]{1,2}->(p2: work_v)
WHERE p1.id = tcp.work_id
),
PaperVector AS (
-- 获取论文对应的向量（ 这里使用 works_vector 表）
SELECT wv.id, wv.vec
FROM work_vec wv
WHERE wv.id IN (SELECT cited_work_id FROM PaperCitationNetwork)
UNION
SELECT wv.id, wv.vec
FROM work_vec wv
WHERE wv.id = (SELECT work_id FROM TopCitedPaper)
),
SimilarityScore AS (
-- 计算论文间的主题向量相似度（ 向量相似度计算）
SELECT pcn.cited_work_id, (wv1.vec <-> wv2.vec) AS similarity_score
FROM PaperCitationNetwork pcn
JOIN PaperVector wv1 ON wv1.id = pcn.cited_work_id
JOIN PaperVector wv2 ON wv2.id = (SELECT work_id FROM TopCitedPaper)
ORDER BY (wv1.vec <-> wv2.vec) ASC
) 
-- 返回贡献度（ 相似度） 最高的论文
SELECT w.title, w.cited_by_count, ss.similarity_score
FROM SimilarityScore ss
JOIN work w ON w.id = ss.cited_work_id
ORDER BY ss.similarity_score ASC
LIMIT 10;