WITH t AS (
-- 第一步： 获取目标作者的合作关系， 并提取合作记录的年份信息
select g.id AS id, g.list AS list
from GRAPH_TABLE(
    academic_net
    MATCH (a:author_v where a.id = 5015704722)-[e:author_author_e]->(b:author_v)
    COLUMNS (b.id,e.list)
) g

),
t2 AS (
SELECT t.id, (t_list.year)::int as year, COUNT(1) AS cnt
FROM t,unnest(json_extract(t.list,'$[*].year')) AS t_list(year)
GROUP BY t.id, year
),
t3 AS (
-- 第三步： 按年份对合作次数进行排序， 并为每个年份生成排名
SELECT id,year,ROW_NUMBER() OVER (PARTITION BY year ORDER BY cnt DESC,id asc) AS rank
FROM t2
) 
-- 最后返回每个年份合作次数最多的前三个合作者
SELECT year, array_agg(id) AS top3_id
FROM t3
WHERE rank <= 3
GROUP BY year;
