with t as MATERIALIZED ( -- 需要加物化提示，告诉agensgraph id 很少 否则 au.id IN (SELECT to_jsonb(id) FROM t) 不会走索引
    SELECT id as id
    FROM   author_doc
    WHERE  doc -> 'display_name_alternatives' @> '"Li Hongbo"'
)

SELECT a.id,
       a.display_name                                          AS author_name,
       g.titles,
       g.cnt                                                    AS paper_cnt
FROM (
        MATCH (au:author_v)<-[e:work_author_e]-(w:work_v)
        WHERE au.id IN (SELECT to_jsonb(id) FROM t)
        WITH au.id AS id, collect(DISTINCT w.title) AS titles,count(DISTINCT w.title) as cnt
        RETURN id, titles,cnt
     ) g
JOIN author a ON a.id = g.id::bigint
ORDER BY a.id;