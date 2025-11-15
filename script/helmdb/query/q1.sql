WITH topic_info AS (
-- 第一步：先获得某领域的id与向量
SELECT t.id,tv.vec
from topic t join topic_vec tv on t.id = tv.id
where t.display_name = 'RNA Methylation and Modification in Gene Expression'
limit 1
),
Potential AS (
-- 第二步： 在作者合作图中查找 2～4 跳的候选作者, 并要求一定不是一跳的作者（已经合作过的）和自己
SELECT DISTINCT b.id 
FROM author au, author_author_gra MATCH (a: author_v)-[: author_author_e]{2,4}->(b: author_v)
WHERE au.display_name = 'Zupei Liu'
and au.id = a.id
AND b.id != a.id
AND b.cited_by_count::int >= 10000
),
CandidateWork AS (
-- 第三步： 找出这些候选作者的在这个领域的作品
SELECT DISTINCT p.id as aid, w.id as wid
FROM Potential p,work_author_gra MATCH (au: author_v)<-[: work_author_e]-(w: work_v),work_doc wd
where p.id = au.id and w.id = wd.id and  wd.topics::jsonb @> json_build_array(json_build_object('id',(select id from topic_info)))::jsonb
)

-- 第四步： 计算最佳n个候选者
SELECT cw.aid as author_id,avg(wv.vec <-> (select vec from topic_info)) as avg_dis
from CandidateWork cw join work_vec wv on cw.wid = wv.id 
group by cw.aid
order by avg(wv.vec <-> (select vec from topic_info)) asc,cw.aid asc
limit 3;
