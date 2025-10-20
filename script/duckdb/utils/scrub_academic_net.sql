-- scrub_academic_net.sql
-- 清理所有悬挂边

-- 1. work_referenced_work_e
DELETE FROM work_referenced_work_e
WHERE start_id NOT IN (SELECT id FROM work_v)
   OR end_id   NOT IN (SELECT id FROM work_v);

-- 2. work_topic_e
DELETE FROM work_topic_e
WHERE start_id NOT IN (SELECT id FROM work_v)
   OR end_id   NOT IN (SELECT id FROM topic_v);

-- 3. work_author_e
DELETE FROM work_author_e
WHERE start_id NOT IN (SELECT id FROM work_v)
   OR end_id   NOT IN (SELECT id FROM author_v);

-- 4. author_author_e
DELETE FROM author_author_e
WHERE start_id NOT IN (SELECT id FROM author_v)
   OR end_id   NOT IN (SELECT id FROM author_v);