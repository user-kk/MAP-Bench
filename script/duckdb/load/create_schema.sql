-- =========================================================
--  DuckDB 建库完整脚本（openalex_duckdb.sql）
--  依赖扩展：json / vector / duckpgq
--  用法：duckdb openalex.duckdb < create_schema.sql
-- =========================================================

/* 1. 加载扩展（首次会自动 INSTALL） */
INSTALL json;
INSTALL vss;
INSTALL duckpgq FROM community;
LOAD json;
LOAD vss;
LOAD duckpgq;


/* 2. 图 schema：academic_net */

/*======================== 顶点表 ========================*/


CREATE TABLE author_v(
        id              BIGINT PRIMARY KEY,
        display_name    TEXT,
        works_count     INT,
        cited_by_count  INT
);


CREATE TABLE topic_v(
        id                   BIGINT PRIMARY KEY,
        display_name         TEXT,
        keywords             TEXT,
        works_count          INT,
        cited_by_count       INT
);

CREATE TABLE work_v(
        id                BIGINT PRIMARY KEY,
        title             TEXT,
        publication_year  INT,
        publication_date  DATE,
        type              TEXT,
        cited_by_count    INT,
        is_retracted      BOOLEAN,
        is_paratext       BOOLEAN
);

/*======================== 边表 ========================*/

CREATE TABLE author_author_e(
        start_id BIGINT,
        end_id   BIGINT,
        cnt      INT,
        list     JSON
);

CREATE TABLE work_author_e(
        start_id       BIGINT,
        end_id         BIGINT,
        author_position TEXT
);

CREATE TABLE work_referenced_work_e(
        start_id BIGINT,
        end_id   BIGINT
);

CREATE TABLE work_topic_e(
        start_id BIGINT,
        end_id   BIGINT,
        score    DOUBLE
);


CREATE PROPERTY GRAPH academic_net
  VERTEX TABLES (
    author_v, work_v, topic_v
  )
  EDGE TABLES (
    work_referenced_work_e
      SOURCE KEY (start_id) REFERENCES work_v(id)
      DESTINATION KEY (end_id) REFERENCES work_v(id)
      LABEL work_referenced_work_e,
    work_topic_e
      SOURCE KEY (start_id) REFERENCES work_v(id)
      DESTINATION KEY (end_id) REFERENCES topic_v(id)
      LABEL work_topic_e,
    work_author_e
      SOURCE KEY (start_id) REFERENCES work_v(id)
      DESTINATION KEY (end_id) REFERENCES author_v(id)
      LABEL work_author_e,
    author_author_e
      SOURCE KEY (start_id) REFERENCES author_v(id)
      DESTINATION KEY (end_id) REFERENCES author_v(id)
      LABEL author_author_e
  );

/* 3. JSON 文档表 */
CREATE TABLE author_doc(
    id  BIGINT PRIMARY KEY,
    doc JSON
);

CREATE TABLE work_doc(
    id  BIGINT PRIMARY KEY,
    doi TEXT,
    doc JSON
);

/* 4. 向量表（vector 扩展 VECTOR 类型） */
CREATE TABLE work_vec (
    id  BIGINT PRIMARY KEY,
    doi TEXT,
    vec FLOAT[384]
);

CREATE TABLE topic_vec(
    id  BIGINT PRIMARY KEY,
    vec FLOAT[384]
);

/* 5. 关系表 */
CREATE TABLE author (
    id                       BIGINT PRIMARY KEY,
    display_name             TEXT,
    works_count              INTEGER,
    cited_by_count           INTEGER,
    last_known_institution   TEXT,
    works_api_url            TEXT,
    updated_date             TIMESTAMP,
    institution_id           BIGINT
);

CREATE TABLE work (
    id                BIGINT PRIMARY KEY,
    doi               TEXT,
    title             TEXT,
    display_name      TEXT,
    publication_year  INTEGER,
    publication_date  TEXT,
    type              TEXT,
    cited_by_count    INTEGER,
    is_retracted      BOOLEAN,
    is_paratext       BOOLEAN,
    cited_by_api_url  TEXT,
    language          TEXT
);

CREATE TABLE topic (
    id                       BIGINT PRIMARY KEY,
    display_name             TEXT,
    subfield_id              TEXT,
    subfield_display_name    TEXT,
    field_id                 TEXT,
    field_display_name       TEXT,
    domain_id                TEXT,
    domain_display_name      TEXT,
    description              TEXT,
    keywords                 TEXT,
    works_api_url            TEXT,
    wikipedia_id             TEXT,
    works_count              INTEGER,
    cited_by_count           INTEGER,
    updated_date             TIMESTAMP
);

CREATE TABLE institution (
    id                          BIGINT PRIMARY KEY,
    ror                         TEXT,
    display_name                TEXT,
    country_code                TEXT,
    type                        TEXT,
    homepage_url                TEXT,
    image_url                   TEXT,
    image_thumbnail_url         TEXT,
    display_name_acronyms       JSON,
    display_name_alternatives   JSON,
    works_count                 INTEGER,
    cited_by_count              INTEGER,
    works_api_url               TEXT,
    updated_date                TIMESTAMP
);