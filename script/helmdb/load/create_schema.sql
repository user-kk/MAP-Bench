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
    EXECUTE format('ALTER DATABASE %I SET ivfflat.probes = 38', _db);
END $$;

-- 重载配置，无需重启
SELECT pg_reload_conf();
/*
    创建openalex的图模式
    其中的topics和concepts是同样的含义，但concepts逐渐被topics代替
*/


--以下四个图共用点表，每个图有自己的边表(在同一个数据库中只要标签相同就会自动复用原本的点表或边表)

CREATE GRAPH work_work_gra(
	work_v VLABEL, --论文顶点表
	work_referenced_work_e ELABEL --论文引用关系，前者引用后者
);

CREATE GRAPH work_topic_gra(
    work_v VLABEL, --论文顶点表
    topic_v VLABEL, --主题顶点表
    work_topic_e ELABEL --论文所属于哪个主题
);


CREATE GRAPH work_author_gra(
    work_v VLABEL, --论文顶点表
    author_v VLABEL, --作者顶点表
    work_author_e ELABEL --论文所属于哪些作者（author_position字段标记为第几作者）
);

CREATE GRAPH author_author_gra(
    author_v VLABEL, --作者顶点表
    author_author_e ELABEL --作者合作关系
);


/*
    创建openalex的文档模式
*/

CREATE DOCUMENTS author_doc( -- [新增的表，从原本的author表中拆出来的]
-- 默认还会生成两个字段
-- id bigint 作者id [主键 对应author.id]
-- doc jsonb 文档模型的数据列 包含以下字段：
--     orcid 作者规范id（最近的小部分作者拥有该属性） 字符串类型 [可选 为原来author表的orcid字段，数据中可能存在也可能不存在(原表为null的对应着json中不存在这个属性)]
--     display_name_alternatives 作者可替换的名字 字符串数组 [为原来author表的display_name_alternatives字段]
);

-- works_document文档表schema
CREATE DOCUMENTS work_doc(
    doi TEXT
-- 默认还会生成两个字段
-- id bigint 文章id [主键 对应work.id]
-- doc jsonb 文档模型的数据列 包含 文章元数据（摘要 语言 卷号 期号 页码等）作者数组 主题数组等
);


/*
    创建openalex的向量模式
*/
-- works_vector向量表schema
CREATE VECTORS work_vec[384](
-- 对应work.id
    doi TEXT
-- 默认还会生成一个字段
-- vec vector[384] 依据works表的title+abstract字段向量编码而来
);
ALTER TABLE work_vec ALTER COLUMN id TYPE bigint;
-- topics_vector向量表schema
CREATE VECTORS topic_vec[384](-- 对应topic.id
    -- 默认还会生成一个字段

-- vec vector[384] 依据topics表的keywords字段（该topic的英文描述）向量编码而来
);
ALTER TABLE topic_vec ALTER COLUMN id TYPE bigint;

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
-- gsql -d postgres -p 5435 -r -f /path/to/create_schema.sql