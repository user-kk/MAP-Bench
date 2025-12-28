CREATE INDEX inst_id_index on author(institution_id);
CREATE INDEX author_name_index on author(display_name);

-- 报错：
-- CREATE INDEX ad_gin_index on author_doc using gin ((doc->'display_name_alternatives'));
CREATE INDEX wd_topic_gin_index on work_doc using gin ((doc->'topics'));


-- 顶点表 B-tree 索引
CREATE INDEX work_v_id_index   ON work_v   USING btree (id);
CREATE INDEX author_v_id_index ON author_v USING btree (id);
CREATE INDEX topic_v_id_index  ON topic_v  USING btree (id);

CREATE INDEX work_doc_id_index   ON work_doc  USING btree (id);
CREATE INDEX author_doc_id_index ON author_doc USING btree (id);

CREATE INDEX work_vec_id_index  ON work_vec  USING btree (id);
CREATE INDEX topic_vec_id_index ON topic_vec USING btree (id);

-- IVFFLAT 近似索引
CREATE INDEX idx_work_vec_l2  ON work_vec
  USING ivfflat (vec vector_l2_ops) WITH (lists = 4096);

CREATE INDEX idx_topic_vec_l2 ON topic_vec
  USING ivfflat (vec vector_l2_ops) WITH (lists = 128);