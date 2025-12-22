CREATE INDEX IF NOT EXISTS topic_vec_hnsw_index on topic_vec using hnsw(vec vector_l2_ops) with (m=8,ef_construction = 32);
CREATE INDEX IF NOT EXISTS work_vec_hnsw_index on work_vec using hnsw(vec vector_l2_ops) with (m=32,ef_construction = 400);

CREATE PROPERTY INDEX idx_author_v_id ON author_v(id);
CREATE PROPERTY INDEX idx_work_v_id ON work_v(id);
CREATE PROPERTY INDEX idx_topic_v_id ON topic_v(id);

CREATE INDEX ad_gin_index on author_doc using gin ((doc->'display_name_alternatives'));
CREATE INDEX inst_id_index on author(institution_id);