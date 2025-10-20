SELECT g.t_id as topic_id ,g.display_name,count(DISTINCT g.w_id) as paper_count
    FROM institution i 
        join author a on i.id = a.institution_id
        join GRAPH_TABLE (academic_net
                MATCH (au:author_v)<-[e1:work_author_e]-(w:work_v)-[e2:work_topic_e]->(t:topic_v)
                COLUMNS (au.id as a_id,t.id as t_id,w.id as w_id,t.display_name )
            ) g on a.id = g.a_id 
    where i.display_name = 'Universität Hamburg'
    GROUP BY g.t_id,g.display_name
    ORDER BY paper_count DESC, topic_id ASC
    LIMIT 10;