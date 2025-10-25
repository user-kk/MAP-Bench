-- duckdb 下列查询会卡死，生成巨量的查询计划，查询不出结果，所以只能手动拆开写
-- select r.id 
-- FROM GRAPH_TABLE(
--     academic_net
--     MATCH  (p1:work_v where p1.id = 4394922388)-[e:work_referenced_work_e]->{1,2}(p2:work_v)
--     COLUMNS (p2.id)
-- ) r

-- 下面的写法也不行，见 https://github.com/cwida/duckpgq-extension/issues/249


WITH r1 AS (
    select g1.id
    FROM GRAPH_TABLE(
        academic_net
        MATCH (p1:work_v where p1.id = 4394922388)-[r1:work_referenced_work_e]->(p2:work_v)-[r2:work_referenced_work_e]->(p3:work_v)
        COLUMNS (p3.id)
    ) g1
),
r2 as (
    select g2.id
    FROM GRAPH_TABLE(
        academic_net
        MATCH (p4:work_v where p4.id = 4394922388)-[r3:work_referenced_work_e]->(p5:work_v)
        COLUMNS (p5.id)
    ) g2
),
r3 as (
    (select g3.id
    FROM GRAPH_TABLE(
        academic_net
        MATCH (p6:work_v where p6.id = 4394922388)
        COLUMNS (p6.id)
    ) g3)
)
select id from r1 union all select id from r2 union all select id from r3
    



explain
SELECT p.title,
       p.publication_year AS year,
       p.cited_by_count AS n_citation
FROM GRAPH_TABLE(
    academic_net
    MATCH (p1:work_v where p1.id = 4394922388)-[r:work_referenced_work_e]->{0,2}(p2:work_v)
    COLUMNS (p2.id)
) r
JOIN work             p  ON p.id = r.id
JOIN work_doc         wd ON wd.id = p.id
ORDER BY p.cited_by_count DESC, p.id ASC;


    --    (
    --     SELECT to_json(array_agg(a.display_name))
    --     FROM 
    --         unnest(json_extract(wd.doc,'$.authorships[*]')) AS author_obj, 
    --         author a                                                  
    --     WHERE 
    --         (author_obj->'unnest'->'author'->'id')::bigint = a.id   
    --    ) AS authors,

explain (format JSON)
select r.id 
FROM GRAPH_TABLE(
    academic_net
    MATCH  p = ANY SHORTEST (p1:work_v where p1.id = 4394922388)-[e:work_referenced_work_e]->{1,2}(p2:work_v)
    COLUMNS (p2.id)
) r


