-- 导入openalex图顶点表的数据
COPY work_v (id,properties)
FROM '/home/hyh/OpenAlex_mini_new/graph/vertices/work_v.csv'
DELIMITER ','
CSV HEADER;


COPY author_v (id,properties)
FROM '/home/hyh/OpenAlex_mini_new/graph/vertices/author_v.csv'
DELIMITER ','
CSV HEADER;

COPY topic_v(id,properties)
FROM '/home/hyh/OpenAlex_mini_new/graph/vertices/topic_v.csv'
DELIMITER ','
CSV HEADER;


-- 导入openalex图边表的数据

-- 导入works_referenced_works边表数据

COPY work_referenced_work_e (startid, endid, properties)
FROM '/home/hyh/OpenAlex_mini_new/graph/edges/work_referenced_work_e.csv'
DELIMITER ','
CSV HEADER;

update work_referenced_work_e set startlabelid = 'work_v'::regclass::bigint , endlabelid = 'work_v'::regclass::bigint;



-- 导入authors_authors边表数据

COPY author_author_e (startid, endid, properties)
FROM '/home/hyh/OpenAlex_mini_new/graph/edges/author_author_e.csv'
DELIMITER ','
CSV HEADER;

update author_author_e set startlabelid = 'author_v'::regclass::bigint , endlabelid = 'author_v'::regclass::bigint;




-- 导入works_topics边表数据

COPY work_topic_e (startid, endid, properties)
FROM '/home/hyh/OpenAlex_mini_new/graph/edges/work_topic_e.csv'
DELIMITER ','
CSV HEADER;

update work_topic_e set startlabelid = 'work_v'::regclass::bigint , endlabelid = 'topic_v'::regclass::bigint;



-- 导入works_authors边表数据

COPY work_author_e (startid, endid, properties)
FROM '/home/hyh/OpenAlex_mini_new/graph/edges/work_author_e.csv'
DELIMITER ','
CSV HEADER;

update work_author_e set startlabelid = 'work_v'::regclass::bigint , endlabelid = 'author_v'::regclass::bigint;




--导入文档表数据
-- works_document文档表导入命令
copy work_doc(id,doi,doc) from '/home/hyh/OpenAlex_mini_new/doc/tiny_works_document_cleaned.csv' WITH (FORMAT csv, DELIMITER ',',HEADER);
create index work_document_id_index on work_doc using hash (id);

-- authors_document文档表导入命令
copy author_doc(id,doc) from '/home/hyh/OpenAlex_mini_new/doc/tiny_authors_document.csv' WITH (FORMAT csv, DELIMITER ',',HEADER);
create index author_document_id_index on author_doc using hash (id);

--导入向量表数据
-- works_vector向量表导入命令
copy work_vec(id,doi,vec) from '/home/hyh/OpenAlex_mini_new/vector/tiny_works_vector.csv' WITH (FORMAT csv, DELIMITER ',',HEADER);
create index work_vector_id_index on work_vec using hash (id);

-- topics_vector向量表导入命令
copy topic_vec(id,vec) from '/home/hyh/OpenAlex_mini_new/vector/tiny_topics_vector.csv' WITH (FORMAT csv, DELIMITER ',',HEADER);
create index topic_vector_id_index on topic_vec using hash (id);

--导入关系表数据
--authors
copy author (id, display_name, works_count, cited_by_count, last_known_institution, works_api_url, updated_date,institution_id)
from '/home/hyh/OpenAlex_mini_new/table/tiny_authors_cleaned.csv'
DELIMITER ','
CSV HEADER;

create index author_id_index on author using hash (id);

--works
copy work (id, doi, title, display_name, publication_year, publication_date, type, cited_by_count, is_retracted, is_paratext, cited_by_api_url, language)
from '/home/hyh/OpenAlex_mini_new/table/tiny_works.csv'
DELIMITER ','
CSV HEADER;

create index work_id_index on work using hash (id);

--topics
copy topic (id, display_name, subfield_id, subfield_display_name, field_id, field_display_name, domain_id, domain_display_name, description, keywords, works_api_url, wikipedia_id, works_count, cited_by_count, updated_date)
from '/home/hyh/OpenAlex_mini_new/table/tiny_topics.csv'
DELIMITER ','
CSV HEADER;

create index topic_id_index on topic using hash (id);

--institutions
copy institution (id, ror, display_name, country_code, type, homepage_url, image_url, image_thumbnail_url, display_name_acronyms, display_name_alternatives, works_count, cited_by_count, works_api_url, updated_date)
from '/home/hyh/OpenAlex_mini_new/table/tiny_institutions.csv'
DELIMITER ','
CSV HEADER;

create index institution_id_index on institution using hash (id);

--institutions_geo
copy institution_geo (institution_id, city, geonames_city_id, region, country_code, country, latitude, longitude)
FROM '/home/hyh/OpenAlex_mini_new/table/tiny_institutions_geo.csv'
DELIMITER ','
CSV HEADER;

create index institution_geo_id_index on institution_geo using hash (institution_id);