SELECT a.id, a.display_name as author_name, jsonb_agg(DISTINCT g.title)::text AS titles,count(DISTINCT g.title) as paper_cnt
FROM (
        MATCH (au:author_v)<-[e:work_author_e]-(w:work_v)
        RETURN au.id, w.title
) g
JOIN author_doc ad ON ad.id = g.id::bigint
JOIN author a      ON a.id  = ad.id
WHERE ad.doc -> 'display_name_alternatives' @> '"Li Hongbo"'
GROUP BY a.id, a.display_name
ORDER BY a.id;