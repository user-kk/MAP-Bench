SELECT t.id AS id,
        count(*) AS cnt
FROM (
    SELECT wc.id AS id
    FROM   work_doc wc
    WHERE  json_contains(wc.doc.topics,
                        '{"display_name":"Economic Implications of Climate Change Policies"}')
    AND  json_contains(wc.doc.topics,
                        '{"display_name":"Economic Impact of Environmental Policies and Resources"}')
) as t join
    GRAPH_TABLE (academic_net
            MATCH (a:work_v)-[e :work_referenced_work_e]->(b:work_v)
            where  a.type = 'article' and a.publication_year >= 2020
            COLUMNS (a.id AS a_id,
                    b.id AS b_id)
    ) g on t.id = g.b_id
GROUP BY t.id
ORDER BY cnt DESC, id ASC
limit 5
