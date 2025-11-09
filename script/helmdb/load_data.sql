-- 1. 基础目录
\set prefix      /home/wzh/data/openalex_middle

-- 2. 拼出每一张表要用的文件路径
\set doc_work        :prefix'/document/works_doc.csv'
\set doc_author      :prefix'/document/authors_doc.csv'
\set vec_work        :prefix'/vector/works_vec.csv'
\set vec_topic       :prefix'/vector/topics_vec.csv'
\set csv_author      :prefix'/csv-files/authors.csv'
\set csv_work        :prefix'/csv-files/works.csv'
\set csv_topic       :prefix'/csv-files/topics.csv'
\set csv_inst        :prefix'/csv-files/institutions.csv'
\set csv_geo         :prefix'/csv-files/institutions_geo.csv'
\set v_author        :prefix'/graph_vertices/authors_v.csv'
\set v_work          :prefix'/graph_vertices/works_v.csv'
\set v_topic         :prefix'/graph_vertices/topics_v.csv'
\set e_author_author :prefix'/graph_edges/authors_authors_e.csv'
\set e_work_author   :prefix'/graph_edges/works_authors_e.csv'
\set e_work_ref      :prefix'/graph_edges/works_referenced_works_e.csv'
\set e_work_topic    :prefix'/graph_edges/works_topics_e.csv'  

/* ======================
   3. 图顶点表导入
   ====================== */
COPY work_v (id, properties)
FROM :'v_work' DELIMITER ',' CSV HEADER;

COPY author_v (id, properties)
FROM :'v_author' DELIMITER ',' CSV HEADER;

COPY topic_v (id, properties)
FROM :'v_topic' DELIMITER ',' CSV HEADER;

-- 顶点表 B-tree 索引
CREATE INDEX work_v_id_index   ON work_v   USING btree (id);
CREATE INDEX author_v_id_index ON author_v USING btree (id);
CREATE INDEX topic_v_id_index  ON topic_v  USING btree (id);

/* ======================
   4. 图边表导入
   ====================== */
-- works ↔ works 引用关系
COPY work_referenced_work_e (startid, endid, properties)
FROM :'e_work_ref' DELIMITER ',' CSV HEADER;
UPDATE work_referenced_work_e
   SET startlabelid = 'work_v'::regclass::bigint,
       endlabelid   = 'work_v'::regclass::bigint;

-- authors ↔ authors
COPY author_author_e (startid, endid, properties)
FROM :'e_author_author' DELIMITER ',' CSV HEADER;
UPDATE author_author_e
   SET startlabelid = 'author_v'::regclass::bigint,
       endlabelid   = 'author_v'::regclass::bigint;

-- works ↔ topics
COPY work_topic_e (startid, endid, properties)
FROM :'e_work_topic' DELIMITER ',' CSV HEADER;
UPDATE work_topic_e
   SET startlabelid = 'work_v'::regclass::bigint,
       endlabelid   = 'topic_v'::regclass::bigint;

-- works ↔ authors
COPY work_author_e (startid, endid, properties)
FROM :'e_work_author' DELIMITER ',' CSV HEADER;
UPDATE work_author_e
   SET startlabelid = 'work_v'::regclass::bigint,
       endlabelid   = 'author_v'::regclass::bigint;

/* ======================
   5. 文档表导入
   ====================== */
COPY work_doc  (id, doi, doc) FROM :'doc_work   WITH (FORMAT csv,' DELIMITER ',', HEADER);
COPY author_doc(id, doc)      FROM :'doc_author WITH (FORMAT csv,' DELIMITER ',', HEADER);

CREATE INDEX work_doc_id_index   ON work_doc  USING btree (id);
CREATE INDEX author_doc_id_index ON author_doc USING btree (id);

/* ======================
   6. 向量表导入
   ====================== */
COPY work_vec  (id, doi, vec) FROM :'vec_work  WITH (FORMAT csv,' DELIMITER ',', HEADER);
COPY topic_vec (id, vec)      FROM :'vec_topic WITH (FORMAT csv,' DELIMITER ',', HEADER);

CREATE INDEX work_vec_id_index  ON work_vec  USING btree (id);
CREATE INDEX topic_vec_id_index ON topic_vec USING btree (id);

-- IVFFLAT 近似索引
CREATE INDEX idx_work_vec_l2  ON work_vec
  USING ivfflat (vec vector_l2_ops) WITH (lists = 80);

CREATE INDEX idx_topic_vec_l2 ON topic_vec
  USING ivfflat (vec vector_l2_ops) WITH (lists = 80);

/* ======================
   7. 关系表（属性表）导入
   ====================== */
COPY author (id, display_name, works_count, cited_by_count,
             last_known_institution, works_api_url, updated_date,
             institution_id)
FROM :'csv_author' DELIMITER ',' CSV HEADER;

COPY work (id, doi, title, display_name, publication_year,
          publication_date, type, cited_by_count, is_retracted,
          is_paratext, cited_by_api_url, language)
FROM :'csv_work' DELIMITER ',' CSV HEADER;

COPY topic (id, display_name, subfield_id, subfield_display_name,
           field_id, field_display_name, domain_id, domain_display_name,
           description, keywords, works_api_url, wikipedia_id,
           works_count, cited_by_count, updated_date)
FROM :'csv_topic' DELIMITER ',' CSV HEADER;

COPY institution (id, ror, display_name, country_code, type,
                 homepage_url, image_url, image_thumbnail_url,
                 display_name_acronyms, display_name_alternatives,
                 works_count, cited_by_count, works_api_url, updated_date)
FROM :'csv_inst' DELIMITER ',' CSV HEADER;

COPY institution_geo (institution_id, city, geonames_city_id,
                     region, country_code, country, latitude, longitude)
FROM :'csv_geo' DELIMITER ',' CSV HEADER;