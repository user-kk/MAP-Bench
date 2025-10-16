/* 0. 扩展 */
INSTALL json;
INSTALL vss;
INSTALL duckpgq FROM community;
LOAD json;
LOAD vss;
LOAD duckpgq;

/* 1. JSON 文档表 – 列序：id, doc | id, doi, doc */
COPY author_doc (id, doc)
FROM '/openalex_middle/document/authors_doc.csv' (HEADER TRUE);

COPY work_doc (id, doi, doc)
FROM '/openalex_middle/document/works_doc.csv' (HEADER TRUE);

/* 2. 向量表 – 列序：id, doi, vec | id, vec */
COPY work_vec (id, doi, vec)
FROM '/openalex_middle/vector/works_vec.csv' (HEADER TRUE);

COPY topic_vec (id, vec)
FROM '/openalex_middle/vector/topics_vec.csv' (HEADER TRUE);

/* 3. 关系表 – 与文件列序完全一致 */
COPY author (id, display_name, works_count, cited_by_count,
             last_known_institution, works_api_url, updated_date,
             institution_id)
FROM '/openalex_middle/csv-files/authors.csv' (HEADER TRUE);

COPY work (id, doi, title, display_name, publication_year,
          publication_date, type, cited_by_count, is_retracted,
          is_paratext, cited_by_api_url, language)
FROM '/openalex_middle/csv-files/works.csv' (HEADER TRUE);

COPY topic (id, display_name, subfield_id, subfield_display_name,
           field_id, field_display_name, domain_id, domain_display_name,
           description, keywords, works_api_url, wikipedia_id,
           works_count, cited_by_count, updated_date)
FROM '/openalex_middle/csv-files/topics.csv' (HEADER TRUE);

COPY institution (id, ror, display_name, country_code, type,
                 homepage_url, image_url, image_thumbnail_url,
                 display_name_acronyms, display_name_alternatives,
                 works_count, cited_by_count, works_api_url, updated_date)
FROM '/openalex_middle/csv-files/institutions.csv' (HEADER TRUE);

COPY institution_geo (institution_id, city, geonames_city_id,
                     region, country_code, country, latitude, longitude)
FROM '/openalex_middle/csv-files/institutions_geo.csv' (HEADER TRUE);

/* 4. 顶点表 – 列序：id, properties */
CREATE TEMP TABLE authors_raw_csv(id BIGINT, properties TEXT);
COPY authors_raw_csv FROM '/openalex_middle/graph_vertices/authors_v.csv' (HEADER TRUE);
INSERT INTO author_v(id, display_name, works_count, cited_by_count)
SELECT id,
       (properties::JSON->>'$.display_name')::TEXT,
       (properties::JSON->>'$.works_count')::INT,
       (properties::JSON->>'$.cited_by_count')::INT
FROM authors_raw_csv;

CREATE TEMP TABLE topics_raw_csv(id BIGINT, properties TEXT);
COPY topics_raw_csv FROM '/openalex_middle/graph_vertices/topics_v.csv' (HEADER TRUE);
INSERT INTO topic_v(id, display_name, keywords, works_count, cited_by_count)
SELECT id,
       (properties::JSON->>'$.display_name')::TEXT,
       (properties::JSON->>'$.keywords')::TEXT,
       (properties::JSON->>'$.works_count')::INT,
       (properties::JSON->>'$.cited_by_count')::INT
FROM topics_raw_csv;

CREATE TEMP TABLE works_raw_csv(id BIGINT, properties TEXT);
COPY works_raw_csv FROM '/openalex_middle/graph_vertices/works_v.csv' (HEADER TRUE);
INSERT INTO work_v(id, title, publication_year, publication_date, type,
                   cited_by_count, is_retracted, is_paratext)
SELECT id,
       (properties::JSON->>'$.title')::TEXT,
       (properties::JSON->>'$.publication_year')::INT,
       CAST(properties::JSON->>'$.publication_date' AS DATE),
       (properties::JSON->>'$.type')::TEXT,
       (properties::JSON->>'$.cited_by_count')::INT,
       (properties::JSON->>'$.is_retracted')::BOOLEAN,
       (properties::JSON->>'$.is_paratext')::BOOLEAN
FROM works_raw_csv;

/* 5. 边表 – 列序：startid, endid, properties */
CREATE TEMP TABLE authors_authors_e_raw_csv(startid BIGINT, endid BIGINT, properties TEXT);
COPY authors_authors_e_raw_csv FROM '/openalex_middle/graph_edges/authors_authors_e.csv' (HEADER TRUE);
INSERT INTO author_author_e(start_id, end_id, cnt, list)
SELECT startid,
       endid,
       (properties::JSON->>'$.cnt')::INT,
       properties::JSON->>'$.list'
FROM authors_authors_e_raw_csv;

CREATE TEMP TABLE works_authors_e_raw_csv(startid BIGINT, endid BIGINT, properties TEXT);
COPY works_authors_e_raw_csv FROM '/openalex_middle/graph_edges/works_authors_e.csv' (HEADER TRUE);
INSERT INTO work_author_e(start_id, end_id, author_position)
SELECT startid,
       endid,
       properties::JSON->>'$.author_position'
FROM works_authors_e_raw_csv;

CREATE TEMP TABLE works_referenced_works_e_raw_csv(startid BIGINT, endid BIGINT, properties TEXT);
COPY works_referenced_works_e_raw_csv FROM '/openalex_middle/graph_edges/works_referenced_works_e.csv' (HEADER TRUE);
INSERT INTO work_referenced_work_e(start_id, end_id)
SELECT startid, endid
FROM works_referenced_works_e_raw_csv;

CREATE TEMP TABLE works_topics_e_raw_csv(startid BIGINT, endid BIGINT, properties TEXT);
COPY works_topics_e_raw_csv FROM '/openalex_middle/graph_edges/works_topics_e.csv' (HEADER TRUE);
INSERT INTO work_topic_e(start_id, end_id, score)
SELECT startid,
       endid,
       (properties::JSON->>'$.score')::DOUBLE
FROM works_topics_e_raw_csv;


-- duckpgq使用csr加速图查询，运行第一次图查询会建立csr结构，建立后只在会话期间存在，不会利用索引
-- 使用duckpgq后建立索引会出现问题，见issue https://github.com/duckdb/duckdb/issues/18190

-- /*======================== 边表索引 ========================*/

-- /* 1. 作者-作者合作边：双向遍历 + 按强度查 */
-- CREATE INDEX idx_aa_src ON author_author_e (start_id);
-- CREATE INDEX idx_aa_dst ON author_author_e (end_id);

-- /* 2. 论文-作者归属边：论文→作者、作者→论文 双向 */
-- CREATE INDEX idx_wa_src ON work_author_e (start_id);
-- CREATE INDEX idx_wa_dst ON work_author_e (end_id);


-- /* 3. 论文-引用-论文边：出引、被引 双向 */
-- CREATE INDEX idx_wr_src ON work_referenced_work_e (start_id);
-- CREATE INDEX idx_wr_dst ON work_referenced_work_e (end_id);

-- /* 4. 论文-主题关联边：论文→主题、主题→论文 双向 */
-- CREATE INDEX idx_wt_src ON work_topic_e (start_id);
-- CREATE INDEX idx_wt_dst ON work_topic_e (end_id);


CREATE INDEX IF NOT EXISTS idx_work_vec_l2
  ON work_vec
  USING HNSW (vec) WITH (metric = 'l2sq', m = 16, ef_construction = 200);

CREATE INDEX IF NOT EXISTS idx_topic_vec_l2
  ON topic_vec
  USING HNSW (vec) WITH (metric = 'l2sq', m = 16, ef_construction = 200);