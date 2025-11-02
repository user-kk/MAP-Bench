with t as MATERIALIZED ( -- 需要加物化提示，告诉agensgraph id 很少 否则 au.id IN (SELECT to_jsonb(id) FROM t) 不会走索引
    SELECT id as id
    FROM   author_doc
    WHERE  doc -> 'display_name_alternatives' @> '"Li Hongbo"'
)

SELECT a.id,
       a.display_name                                          AS author_name,
       jsonb_agg(DISTINCT g.title)::text                       AS titles,
       count(DISTINCT g.title)                                 AS paper_cnt
FROM (
        MATCH (au:author_v)<-[e:work_author_e]-(w:work_v)
        WHERE au.id IN (SELECT to_jsonb(id) FROM t)
        RETURN au.id, w.title
     ) g
JOIN author a ON a.id = g.id::bigint
GROUP BY a.id, a.display_name
ORDER BY a.id;