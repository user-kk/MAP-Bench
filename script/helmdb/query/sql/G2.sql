-- @a_id, @b_id表示给定的两篇论文
WITH t AS (
    -- 第一步：计算两篇论文之间的最短路径(不含起点终点)
    SELECT e.endid AS p_id
    FROM work_work_gra MATCH SHORTEST path = (p1: work_v)-[e: work_referenced_work_e] * -> (p2: work_v)
    WHERE p1.id = 4377013841 AND p2.id = 3155434940 
),
PaperDetails AS (
    -- 第二步：获取路径论文的被引量和 authorships 数组
    SELECT 
        t.p_id, 
        w.cited_by_count AS paper_cites,
        wd.authorships::jsonb AS authorships_jsonb 
    FROM t
    JOIN work w ON w.id = t.p_id
    JOIN work_doc wd ON wd.id = t.p_id
    where t.p_id != 4377013841 and t.p_id != 3155434940
),
t2 as (
    -- 第三步：根据影响力计算公式计算影响力
    SELECT 
        pd.p_id as id,
        p.title,
        -- 影响力计算公式（示例）：论文被引量 + sqrt(作者平均影响力)
        (pd.paper_cites + sqrt(COALESCE((
            -- 计算作者平均影响力
            SELECT AVG(a.cited_by_count) 
            FROM 
                jsonb_array_elements(pd.authorships_jsonb) AS author_obj, -- 1. 将 authorships 数组展开
                author a                                                   -- 2. 关联 author 表
            WHERE 
                (author_obj.author.id)::bigint = a.id              -- 3. 从嵌套JSON中提取id进行关联
        ), 0))) AS influence_score
    FROM PaperDetails pd
    JOIN work p ON p.id = pd.p_id
)
select id, title from t2 
ORDER BY influence_score DESC,id asc;