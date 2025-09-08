-- 开启一个事务
BEGIN;

-- 1. 创建新的作者 (保持不变)
INSERT INTO author (id, display_name, works_count, cited_by_count) VALUES
(9000000001, 'Friend A', 1, 1),
(9000000002, 'Friend B', 1, 1),
(9000000003, 'Potential Collaborator', 1, 10);

-- 2. 将新作者添加到图的顶点表 (保持不变)
INSERT INTO author_v (id, properties) VALUES
(9000000001, '{"display_name": "Friend A", "works_count": 1, "cited_by_count": 1}'),
(9000000002, '{"display_name": "Friend B", "works_count": 1, "cited_by_count": 1}'),
(9000000003, '{"display_name": "Potential Collaborator", "works_count": 1, "cited_by_count": 10}');

-- 3. 创建作者之间的合作关系 (边) (保持不变)
DO $$
DECLARE
    sander_id bigint;
BEGIN
    SELECT id INTO sander_id FROM author WHERE display_name = 'Sander R. Dahmen' LIMIT 1;
    
    INSERT INTO author_author_e (startid, endid, properties) VALUES
    (sander_id, 9000000001, '{}'),
    (9000000001, 9000000002, '{}'),
    (9000000002, 9000000003, '{}');
END $$;

-- 4. 核心修正点: 手动更新边表的 labelid 来“注册”新边
-- 这个操作让 MATCH 查询能够“看到”我们刚刚 INSERT 的边
UPDATE author_author_e SET startlabelid = 'author_v'::regclass::bigint, endlabelid = 'author_v'::regclass::bigint WHERE startlabelid IS NULL;


-- 5. 创建新的研究主题、向量、论文等 (这部分逻辑保持不变)
INSERT INTO topic (id, display_name) VALUES (8000000001, 'Data Science');
INSERT INTO topic_v (id, properties) VALUES (8000000001, '{"display_name": "Data Science"}');

DO $$
DECLARE
    vec_array double precision[];
    vec_string text;
BEGIN
    SELECT array_agg(0.5) INTO vec_array FROM generate_series(1, 128);
    SELECT array_to_string(vec_array, ',') INTO vec_string;
    INSERT INTO topic_vec (id, vec) VALUES (8000000001, CAST('[' || vec_string || ']' AS vector));
END $$;

INSERT INTO work (id, title, display_name, cited_by_count) VALUES
(7000000001, 'Another Paper on Data Science', 'Another Paper on Data Science', 1),
(7000000002, 'A Paper on Data Science', 'A Paper on Data Science', 1);
INSERT INTO work_v (id, properties) VALUES
(7000000001, '{"title": "Another Paper on Data Science"}'),
(7000000002, '{"title": "A Paper on Data Science"}');

DO $$
DECLARE
    sander_id bigint;
BEGIN
    SELECT id INTO sander_id FROM author WHERE display_name = 'Sander R. Dahmen' LIMIT 1;
    INSERT INTO work_author_e (startid, endid, properties) VALUES (7000000001, sander_id, '{"author_position": "first"}');
    INSERT INTO work_author_e (startid, endid, properties) VALUES (7000000002, 9000000003, '{"author_position": "first"}');
END $$;

-- 同样，为新插入的 work_author_e 边也执行 UPDATE
UPDATE work_author_e SET startlabelid = 'work_v'::regclass::bigint, endlabelid = 'author_v'::regclass::bigint WHERE startlabelid IS NULL;


INSERT INTO work_topic_e (startid, endid, properties) VALUES
(7000000001, 8000000001, '{"score": 1.0}'),
(7000000002, 8000000001, '{"score": 1.0}');

-- 同样，为新插入的 work_topic_e 边也执行 UPDATE
UPDATE work_topic_e SET startlabelid = 'work_v'::regclass::bigint, endlabelid = 'topic_v'::regclass::bigint WHERE startlabelid IS NULL;


COMMIT;