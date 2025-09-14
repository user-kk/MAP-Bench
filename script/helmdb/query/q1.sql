WITH Potential AS (
-- 第一步： 在作者图中查找 2～ 3 跳的候选作者, 并要求一定不是一跳的作者和自己
SELECT DISTINCT b.id 
FROM author_author_graph MATCH (a: author_v)-[: author_author_e]{2,3}-(b: author_v)
WHERE a.display_name = 'Zupei Liu'
AND b.cited_by_count >= 0 
AND b.id != a.id
),
CandidateTopics AS (
-- 第二步： 找出这些候选作者关联到的全部 topic_id对应的向量
SELECT tmp1.candidate_id , tv1.vec
FROM (
    SELECT DISTINCT p.id as candidate_id, t.id as topic_id
    FROM Potential p,
        work_author_graph MATCH (au: author_v)<-[: work_author_e]-(w1: work_v), work_topic_gra MATCH (w2: work_v)-[: work_topic_e]->(t: topic_v)
    WHERE au.id = p.id and w1.id =w2.id
) as tmp1 , topic_vec as tv1
WHERE tmp1.topic_id = tv1.id
),


-- 原作者的所有topic_id对应的向量
CurrentAuthorTopics AS (
SELECT tmp2.candidate_id , tv2.vec
from (
    SELECT DISTINCT au.id as candidate_id, t.id as topic_id
    FROM work_author_graph MATCH (au: author_v)<-[: work_author_e]-(w1: work_v),
        work_topic_gra MATCH (w2: work_v)-[: work_topic_e ]->(t: topic_v)
    WHERE au.display_name = 'Zupei Liu' and w1.id =w2.id
) as tmp2 , topic_vec as tv2
WHERE tmp2.topic_id = tv2.id

)
-- 第三步： 计算最佳n个候选者
SELECT ct.candidate_id
from CurrentAuthorTopics cat,
    CandidateTopics ct
group by cat.candidate_id,ct.candidate_id
order by avg(cat.vec <-> ct.vec) asc
limit 3;
