SELECT a.id, a.display_name as author_name,to_json(array_agg(DISTINCT g.title)) as titles,count(DISTINCT g.title) as paper_cnt
FROM author_doc ad
JOIN author a ON ad.id = a.id
JOIN GRAPH_TABLE (
        academic_net
        MATCH (au:author_v)<-[e:work_author_e]-(w:work_v)
        COLUMNS (au.id, w.title)
    ) g on a.id = g.id
WHERE json_contains(ad.doc->'display_name_alternatives', '"Li Hongbo"')
GROUP by a.id, a.display_name
order by a.id

