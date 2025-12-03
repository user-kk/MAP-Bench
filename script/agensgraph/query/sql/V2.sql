with tids as (
    select id,tv.vec <-> (select vec from topic_vec where id = 10862) as dis
    from topic_vec tv
    order by tv.vec <-> (select vec from topic_vec where id = 10862) asc
    limit 5
),
topicWork as (
    select tids.id,tids.dis,g.title,ROW_NUMBER() OVER (PARTITION BY tids.id ORDER BY g.cited_by_count::int DESC,g.wid asc) AS rank
    from (
        MATCH (w: work_v)-[:work_topic_e]->(t: topic_v)
        where t.id in (select to_jsonb(id) from tids) and t.works_count > 10000
        return w.id as wid,w.title,w.cited_by_count,t.id as tid
    ) g join tids on g.tid::bigint = tids.id
)

select t.display_name,json_agg(tw.title order by tw.rank) as top_papers_json
    from topicWork tw join topic t on tw.id = t.id
    where tw.rank<=3
    group by t.display_name,tw.dis
    order by tw.dis asc