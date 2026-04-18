with tids as (
    select id,array_distance(tv.vec,(select vec from topic_vec where id = __MB_seed_topic_id__)) as dis
    from topic_vec tv
    order by dis asc
    limit 5
),
topicWork as (
    select tids.id,tids.dis,g.title,ROW_NUMBER() OVER (PARTITION BY tids.id ORDER BY g.cited_by_count::int DESC,g.wid asc) AS rank
    from tids join
    GRAPH_TABLE (
        academic_net
        MATCH (w: work_v)-[e:work_topic_e]->(t: topic_v)
        where t.id in (select id from tids) and t.works_count > 10000
        COLUMNS (w.id as wid,w.title,w.cited_by_count,t.id as tid)
    ) g on tids.id = g.tid
)

select t.display_name,array_agg(tw.title order by tw.rank)
    from topicWork tw join topic t on tw.id = t.id
    where tw.rank<=3
    group by t.display_name,tw.dis
    order by tw.dis asc