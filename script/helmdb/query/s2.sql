WITH TargetTopicWorks AS (
    -- 第一步：用图模型找到目标主题下的所有论文
    SELECT DISTINCT w1.id AS work_id
    FROM work_topic_gra MATCH (w1: work_v)-[: work_topic_e]->(t: topic_v)
    WHERE t.properties->>'display_name' = @topic_name
),
TargetTopicWorkDetails AS (
    -- 第二步：用关系模型获取这些论文的详细信息
    SELECT w.id, w.title, w.cited_by_count, w.publication_year
    FROM TargetTopicWorks tw,
         work w
    WHERE w.id = tw.work_id
)
-- 第三步：按引用量排序并返回结果
SELECT *
FROM TargetTopicWorkDetails
ORDER BY cited_by_count DESC
LIMIT 10;