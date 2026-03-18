CREATE INDEX IF NOT EXISTS topic_vec_hnsw_index on topic_vec using hnsw(vec vector_l2_ops) with (m=8,ef_construction = 32);
CREATE INDEX IF NOT EXISTS work_vec_hnsw_index on work_vec using hnsw(vec vector_l2_ops) with (m=8,ef_construction = 64);

CREATE PROPERTY INDEX idx_author_v_id ON author_v(id);
CREATE PROPERTY INDEX idx_work_v_id ON work_v(id);
CREATE PROPERTY INDEX idx_topic_v_id ON topic_v(id);

CREATE INDEX ad_gin_index on author_doc using gin ((doc->'display_name_alternatives'));
CREATE INDEX wd_topic_gin_index on work_doc using gin ((doc->'topics'));

CREATE INDEX inst_id_index on author(institution_id);
CREATE INDEX author_name_index on author(display_name);

-- nLists	2048
-- nProbe	38
-- m	8
-- ef_construction	64
-- ef_search	102