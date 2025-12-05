WITH topic_info AS (
-- 第一步：先获得某领域的id与向量
SELECT t.id,tv.vec
from topic t join topic_vec tv on t.id = tv.id
where t.display_name = 'RNA Methylation and Modification in Gene Expression'
limit 1
),
Potential AS (
-- 第二步： 在作者合作图中查找 2～4 跳的候选作者, 并要求一定不是一跳的作者（已经合作过的）和自己
MATCH (me:author_v)-[:author_author_e*2..4]->(cand:author_v)
WHERE me.id = (
    SELECT to_jsonb(au.id)
    FROM author au
    WHERE au.display_name = 'Zupei Liu'
) AND cand.cited_by_count >= 10000
return DISTINCT cand.id 
),
CandidateWork AS (
-- 第三步： 找出这些候选作者的在这个领域的作品
SELECT t.aid::bigint as aid, wd.id as wid
FROM (
    MATCH (au: author_v)<-[: work_author_e]-(w: work_v)
    where au.id in (
        select to_jsonb(p.id) from Potential p
    )
    return au.id as aid,w.id as wid
) t join work_doc wd on t.wid::bigint = wd.id 
where wd.doc->'topics' @> jsonb_build_array(jsonb_build_object('id',(select id from topic_info)))
)
-- 第四步： 计算最佳n个候选者
SELECT cw.aid as author_id,avg(wv.vec <-> (select vec from topic_info)) as avg_dis
from CandidateWork cw join work_vec wv on cw.wid = wv.id 
group by cw.aid
order by avg(wv.vec <-> (select vec from topic_info)) asc,cw.aid asc
limit 3;
