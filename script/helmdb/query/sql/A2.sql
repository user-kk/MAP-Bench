WITH t AS (
-- 第一步： 获取目标作者的合作关系， 并提取合作记录的年份信息
SELECT b.id AS id, e.list::jsonb AS list
FROM author_author_gra MATCH (a: author_v)-[e: author_author_e]-(b: author_v)
WHERE a.id = __MB_author_id__
),
t2 AS (
-- 第二步： 统计每个合作关系中的年份， 计算该年份内的合作次数
SELECT t.id, t_list.year::int as year, COUNT(1) AS cnt
FROM t
UNWIND jsonb_array_elements(t.list) AS t_list
GROUP BY t.id, t_list.year::int
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