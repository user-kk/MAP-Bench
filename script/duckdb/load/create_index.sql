/* 1. 加载扩展（首次会自动 INSTALL） */
INSTALL json;
INSTALL vss;
INSTALL duckpgq FROM community;
LOAD json;
LOAD vss;
LOAD duckpgq;


-- 使用duckpgq1.3.2后建立索引会出现问题，见issue https://github.com/duckdb/duckdb/issues/18190

-- /*======================== 边表索引 ========================*/

CREATE INDEX inst_id_index on author(institution_id);
CREATE INDEX author_name_index on author(display_name);

|-- /* 1. 作者-作者合作边：双向遍历 + 按强度查 */
CREATE INDEX idx_aa_src ON author_author_e (start_id);
CREATE INDEX idx_aa_dst ON author_author_e (end_id);

/* 2. 论文-作者归属边：论文→作者、作者→论文 双向 */
CREATE INDEX idx_wa_src ON work_author_e (start_id);
CREATE INDEX idx_wa_dst ON work_author_e (end_id);


/* 3. 论文-引用-论文边：出引、被引 双向 */
CREATE INDEX idx_wr_src ON work_referenced_work_e (start_id);
CREATE INDEX idx_wr_dst ON work_referenced_work_e (end_id);

/* 4. 论文-主题关联边：论文→主题、主题→论文 双向 */
CREATE INDEX idx_wt_src ON work_topic_e (start_id);
CREATE INDEX idx_wt_dst ON work_topic_e (end_id);


SET hnsw_enable_experimental_persistence = true;

CREATE INDEX IF NOT EXISTS idx_work_vec_l2
  ON work_vec
  USING HNSW (vec) WITH (metric = 'l2sq', m = 8, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_topic_vec_l2
  ON topic_vec
  USING HNSW (vec) WITH (metric = 'l2sq', m = 8, ef_construction = 32);