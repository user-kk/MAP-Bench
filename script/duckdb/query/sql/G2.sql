WITH t AS (
    select work_v.id
    from GRAPH_TABLE(
        academic_net
        MATCH p = ANY SHORTEST (p1:work_v where p1.id = __MB_a_id__)-[e:work_referenced_work_e]->*(p2:work_v where p2.id = __MB_b_id__)
        COLUMNS (vertices(p) as node_ids)
    ) g cross join unnest(g.node_ids) as n(rowid) join work_v on n.rowid = work_v.rowid
    where work_v.id <> __MB_a_id__ and work_v.id <> __MB_b_id__
),
PaperDetails AS (
    -- 第二步：获取路径论文的被引量和 authorships 数组
    SELECT 
        t.id, 
        w.cited_by_count AS paper_cites,
        wd.doc->'authorships' AS authorships_jsonb 
    FROM t
    JOIN work w ON w.id = t.id
    JOIN work_doc wd ON wd.id = t.id
),
t2 as (
    -- 第三步：根据影响力计算公式计算影响力
    SELECT 
        pd.id,
        p.title,
        -- 影响力计算公式（示例）：论文被引量 + sqrt(作者平均影响力)
        (pd.paper_cites + SQRT(COALESCE((
            -- 计算作者平均影响力
            SELECT AVG(a.cited_by_count) 
            FROM 
                unnest(json_extract(pd.authorships_jsonb,'$[*].author.id')) as author_obj(id),
                author a                                                   -- 2. 关联 author 表
            WHERE 
                author_obj.id::bigint = a.id              -- 3. 从嵌套JSON中提取id进行关联
        ), 0))) AS influence_score
    FROM PaperDetails pd
    JOIN work p ON p.id = pd.id
)
select id, title from t2 
ORDER BY influence_score DESC,id asc;