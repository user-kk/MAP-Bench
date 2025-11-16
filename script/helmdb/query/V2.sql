with tids as (
    select id,tv.vec <-> (select vec from topic_vec where id = 10862) as dis
    from topic_vec tv
    order by tv.vec <-> (select vec from topic_vec where id = 10862) asc
    limit 5
),
topicWork as (
    select tids.id,tids.dis,w.title ,ROW_NUMBER() OVER (PARTITION BY tids.id ORDER BY w.cited_by_count::int DESC,w.id asc) AS rank
    from tids, work_topic_gra MATCH (w: work_v)-[:work_topic_e]->(t: topic_v)
    where tids.id = t.id and t.works_count > 10000
)

select t.display_name,json_agg(tw.title)
    from topicWork tw join topic t on tw.id = t.id
    where tw.rank<=3
    group by t.display_name,tw.dis
    order by tw.dis asc