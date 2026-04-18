SELECT t.id, t.author_name, json_agg(DISTINCT w.title) AS titles,count(DISTINCT w.title) as paper_cnt
FROM (
    select a.id , a.display_name as author_name
    from author_doc ad join author a on ad.id = a.id
    where ad.display_name_alternatives::jsonb @> '"__MB_author_name__"'
) t, work_author_gra MATCH (au: author_v)<-[e: work_author_e]-(w: work_v)
where t.id = au.id 
GROUP BY t.id, t.author_name
ORDER BY t.id;