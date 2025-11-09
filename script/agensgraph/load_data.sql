-- 1. 基础目录
\set prefix      /openalex_middle

-- 2. 拼出每一张表要用的文件路径
\set doc_work           :prefix'/document/works_doc.csv'
\set doc_author         :prefix'/document/authors_doc.csv'
\set vec_work           :prefix'/vector/works_vec.csv'
\set vec_topic          :prefix'/vector/topics_vec.csv'
\set csv_author         :prefix'/csv-files/authors.csv'
\set csv_work           :prefix'/csv-files/works.csv'
\set csv_topic          :prefix'/csv-files/topics.csv'
\set csv_inst           :prefix'/csv-files/institutions.csv'
\set csv_geo            :prefix'/csv-files/institutions_geo.csv'
\set v_author           :prefix'/graph_vertices/authors_v.csv'
\set v_work             :prefix'/graph_vertices/works_v.csv'
\set v_topic            :prefix'/graph_vertices/topics_v.csv'
\set e_author_author    :prefix'/graph_edges/authors_authors_e.csv'
\set e_work_author      :prefix'/graph_edges/works_authors_e.csv'
\set e_work_ref         :prefix'/graph_edges/works_referenced_works_e.csv'
\set e_work_topic       :prefix'/graph_edges/works_topics_e.csv'  

-- 3. 导入文档表
COPY work_doc(id,doi,doc) FROM :'doc_work'   (FORMAT csv, DELIMITER ',', HEADER);

COPY author_doc(id,doc)   FROM :'doc_author' (FORMAT csv, DELIMITER ',', HEADER);

-- 4. 导入向量表
COPY work_vec(id,doi,vec)  FROM :'vec_work'  (FORMAT csv, DELIMITER ',', HEADER);

COPY topic_vec(id,vec)     FROM :'vec_topic' (FORMAT csv, DELIMITER ',', HEADER);
-- 5. 导入关系表
COPY author(id,display_name,works_count,cited_by_count,last_known_institution,works_api_url,updated_date,institution_id)
FROM :'csv_author' DELIMITER ',' CSV HEADER;

COPY work(id,doi,title,display_name,publication_year,publication_date,type,cited_by_count,is_retracted,is_paratext,cited_by_api_url,language)
FROM :'csv_work' DELIMITER ',' CSV HEADER;

COPY topic(id,display_name,subfield_id,subfield_display_name,field_id,field_display_name,domain_id,domain_display_name,description,keywords,works_api_url,wikipedia_id,works_count,cited_by_count,updated_date)
FROM :'csv_topic' DELIMITER ',' CSV HEADER;

COPY institution(id,ror,display_name,country_code,type,homepage_url,image_url,image_thumbnail_url,display_name_acronyms,display_name_alternatives,works_count,cited_by_count,works_api_url,updated_date)
FROM :'csv_inst' DELIMITER ',' CSV HEADER;

COPY institution_geo(institution_id,city,geonames_city_id,region,country_code,country,latitude,longitude)
FROM :'csv_geo' DELIMITER ',' CSV HEADER;

-- 6. 向量索引
CREATE INDEX IF NOT EXISTS idx_work_vec_l2  ON work_vec  USING ivfflat (vec vector_l2_ops) WITH (lists=80);
CREATE INDEX IF NOT EXISTS idx_topic_vec_l2 ON topic_vec USING ivfflat (vec vector_l2_ops) WITH (lists=80);



CREATE EXTENSION IF NOT EXISTS file_fdw;
CREATE SERVER IF NOT EXISTS csv_server FOREIGN DATA WRAPPER file_fdw;

SET graph_path = academic_net;

DROP FOREIGN TABLE IF EXISTS
        author_v_csv,
        work_v_csv,
        topic_v_csv,
        author_author_e_csv,
        work_author_e_csv,
        work_referenced_work_e_csv,
        work_topic_e_csv;

-- 3. 顶点外部表 ----------------------------------------------------------
CREATE FOREIGN TABLE author_v_csv(
  id bigint,
  properties jsonb
) SERVER csv_server
OPTIONS (format 'csv', header 'true', filename :'v_author', delimiter ',');

CREATE FOREIGN TABLE work_v_csv(
  id bigint,
  properties jsonb
) SERVER csv_server
OPTIONS (format 'csv', header 'true', filename :'v_work',   delimiter ',');

CREATE FOREIGN TABLE topic_v_csv(
  id bigint,
  properties jsonb
) SERVER csv_server
OPTIONS (format 'csv', header 'true', filename :'v_topic',  delimiter ',');

-- 4. 边外部表 -------------------------------------------------------------
CREATE FOREIGN TABLE author_author_e_csv(
  start_id bigint,
  end_id   bigint,
  properties jsonb
) SERVER csv_server
OPTIONS (format 'csv', header 'true', filename :'e_author_author', delimiter ',');

CREATE FOREIGN TABLE work_author_e_csv(
  start_id bigint,
  end_id   bigint,
  properties jsonb
) SERVER csv_server
OPTIONS (format 'csv', header 'true', filename :'e_work_author',   delimiter ',');

CREATE FOREIGN TABLE work_referenced_work_e_csv(
  start_id bigint,
  end_id   bigint,
  properties jsonb
) SERVER csv_server
OPTIONS (format 'csv', header 'true', filename :'e_work_ref',      delimiter ',');

CREATE FOREIGN TABLE work_topic_e_csv(
  start_id bigint,
  end_id   bigint,
  properties jsonb
) SERVER csv_server
OPTIONS (format 'csv', header 'true', filename :'e_work_topic',    delimiter ',');

LOAD FROM author_v_csv AS row
CREATE (a:author_v) SET a = row.properties, a.id = row.id;

LOAD FROM work_v_csv AS row
CREATE (w:work_v) SET w = row.properties, w.id = row.id;

LOAD FROM topic_v_csv AS row
CREATE (t:topic_v) SET t = row.properties, t.id = row.id;

LOAD FROM author_author_e_csv AS row
MATCH (u:author_v {id:row.start_id}), (v:author_v {id:row.end_id})
WHERE u IS NOT NULL AND v IS NOT NULL
CREATE (u)-[e:author_author_e]->(v) SET e = row.properties, e.from = row.start_id, e.to = row.end_id ;

LOAD FROM work_author_e_csv AS row
MATCH (w:work_v {id:row.start_id}), (a:author_v {id:row.end_id})
WHERE w IS NOT NULL AND a IS NOT NULL
CREATE (w)-[e:work_author_e]->(a) SET e = row.properties, e.from = row.start_id, e.to = row.end_id ;

LOAD FROM work_referenced_work_e_csv AS row
MATCH (w1:work_v {id:row.start_id}), (w2:work_v {id:row.end_id})
WHERE w1 IS NOT NULL AND w2 IS NOT NULL
CREATE (w1)-[e:work_referenced_work_e]->(w2) SET e = row.properties, e.from = row.start_id, e.to = row.end_id ;

LOAD FROM work_topic_e_csv AS row
MATCH (w:work_v {id:row.start_id}), (t:topic_v {id:row.end_id})
WHERE w IS NOT NULL AND t IS NOT NULL
CREATE (w)-[e:work_topic_e]->(t) SET e = row.properties, e.from = row.start_id, e.to = row.end_id ;



DROP FOREIGN TABLE IF EXISTS
        author_v_csv,
        work_v_csv,
        topic_v_csv,
        author_author_e_csv,
        work_author_e_csv,
        work_referenced_work_e_csv,
        work_topic_e_csv;
DROP SERVER IF EXISTS csv_server CASCADE;

CREATE PROPERTY INDEX idx_author_v_id ON author_v(id);
CREATE PROPERTY INDEX idx_work_v_id ON work_v(id);
CREATE PROPERTY INDEX idx_topic_v_id ON topic_v(id);