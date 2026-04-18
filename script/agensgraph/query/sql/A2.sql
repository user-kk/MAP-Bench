WITH t AS (
-- 第一步： 获取目标作者的合作关系， 并提取合作记录的年份信息
MATCH (a:author_v {id: __MB_author_id__})-[e:author_author_e]->(b:author_v)
RETURN b.id AS id, e.list AS list
),
t2 AS (
-- 第二步： 统计每个合作关系中的年份， 计算该年份内的合作次数
SELECT t.id, (t_list->>'year')::int as year, COUNT(1) AS cnt
FROM t join LATERAL jsonb_array_elements(t.list) AS t_list on true
GROUP BY t.id, (t_list->>'year')::int
),
t3 AS (
-- 第三步： 按年份对合作次数进行排序， 并为每个年份生成排名
SELECT id,year,ROW_NUMBER() OVER (PARTITION BY year ORDER BY cnt DESC,id asc) AS rank
FROM t2
) 
-- 最后返回每个年份合作次数最多的前三个合作者
SELECT year, json_agg(id) AS top3_id
FROM t3
WHERE rank <= 3
GROUP BY year;