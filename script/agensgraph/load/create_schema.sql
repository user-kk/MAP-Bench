-- 数据库基本设置
SET statement_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
DO $$
DECLARE
    _db text := current_database();
BEGIN
    EXECUTE format('ALTER DATABASE %I SET hnsw.ef_search = 102', _db);
END $$;



CREATE GRAPH academic_net; 

SELECT 'ALTER DATABASE '||quote_ident(current_database())||' SET graph_path TO academic_net;' \gexec

CREATE VLABEL work_v;   
CREATE VLABEL topic_v;   
CREATE VLABEL author_v;   
CREATE ELABEL work_referenced_work_e;
CREATE ELABEL work_topic_e;
CREATE ELABEL work_author_e;
CREATE ELABEL author_author_e;


/*
    创建openalex的文档模式
*/

CREATE TABLE author_doc( 
    id bigint primary key,
    doc jsonb
);

CREATE TABLE work_doc(
    id bigint primary key,
    doc jsonb,
    doi TEXT
);

/*
    创建openalex的向量模式
*/

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE work_vec (
    id bigint primary key,
    doi TEXT,
    vec vector(384)
);

CREATE TABLE topic_vec(
    id bigint primary key,
    vec vector(384)
);

/*
    创建openalex的关系模式
*/

--authors关系表schema
CREATE TABLE author (
    id bigint primary key, -- 作者id
    display_name text,-- 作者名字
    works_count integer, -- 文章数量
    cited_by_count integer, -- 总引用数量
    last_known_institution text, -- 作者所属的最新机构网址
    works_api_url text, -- 文章api网址
    updated_date timestamp without time zone, -- 更新时间
    institution_id bigint -- 机构id [原来为text ，修改为bigint]
);


-- works关系表schema
CREATE TABLE work (
    id bigint primary key, -- 文章id
    doi text, -- doi编号
    title text, -- 文章标题
    display_name text, -- 文章名
    publication_year integer, -- 出版年份
    publication_date text, -- 出版具体日期
    type text, -- 文章类型topic
    cited_by_count integer, -- 被引用数量
    is_retracted boolean, -- 是否被撤稿
    is_paratext boolean, -- 是否是副文本（不报告主要内容）
    cited_by_api_url text, -- api主页
    language text -- 文章语言
);

-- topics关系表schema
CREATE TABLE topic (
    id bigint primary key, -- 主题id
    display_name text, -- 主题名
    subfield_id text, -- 所属父领域subfieldid（openalex所属父领域网址）
    subfield_display_name text, -- 父领域subfield名
    field_id text, -- 所属祖父领域fieldid（openalex祖父领域网址）
    field_display_name text, -- 祖父领域field名
    domain_id text, -- 所属最高一级domainid（openalex的domain领域网址）
    domain_display_name text, -- domain名
    description text, -- 本主题描述
    keywords text, -- 本主题关键字
    works_api_url text, -- 本主题的api网址
    wikipedia_id text, -- 本主题的wikipedia网址
    works_count integer, -- 本主题的所有文章数量
    cited_by_count integer, -- 本主题的被引用数量
    updated_date timestamp without time zone -- 更新时间
);

-- institutions关系表schema
CREATE TABLE institution (
    id bigint primary key, -- 机构id
    ror text, -- ror主页地址
    display_name text, -- 机构名
    country_code text, -- 所属国家简称
    type text, -- 机构类型
    homepage_url text, -- 机构主页网址
    image_url text, -- 机构logo网址
    image_thumbnail_url text, -- 机构logo缩略图网址
    display_name_acronyms json, -- 机构简称
    display_name_alternatives json, -- 机构全称
    works_count integer, -- 机构的文章数量
    cited_by_count integer, -- 机构文章被引用的数量
    works_api_url text, -- 机构api网址
    updated_date timestamp without time zone -- 更新时间
);

-- institutions_geo关系表schema
CREATE TABLE institution_geo (
    institution_id bigint primary key, -- 机构id
    city text, -- 机构所属城市名
    geonames_city_id text, -- 城市id
    region text, -- 机构所属地区
    country_code text, -- 机构所属国家简称
    country text, -- 机构所属国家全称
    latitude real, -- 机构纬度
    longitude real -- 机构经度
);



--示例用法
-- psql -U agensgraph -d openalex_mini -p 5555 -f ./create_schema.sql