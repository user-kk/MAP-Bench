INSTALL json;
LOAD json;


CREATE TABLE new_work_doc (
    id                    BIGINT PRIMARY KEY,
    doi                   VARCHAR,
    doc struct (
        language              VARCHAR,
        abstract              VARCHAR,
        volume                VARCHAR,
        issue                 VARCHAR,
        first_page            VARCHAR,
        last_page             VARCHAR,
        abstract_inverted_index MAP(VARCHAR, INT[]),
        topics                STRUCT(id BIGINT, score DOUBLE, display_name VARCHAR)[],
        authorships           STRUCT(
                                author_position VARCHAR,
                                author STRUCT(id BIGINT, display_name VARCHAR),
                                institution STRUCT(id BIGINT, display_name VARCHAR)
                            )[]
    )
    
);

-- 1. 迁移数据（元素级全部补 NULL）
INSERT INTO new_work_doc
SELECT
    w.id,
    w.doi,
    {
        language : coalesce(json_extract(w.doc, '$.language'), NULL),
        abstract : coalesce(json_extract(w.doc, '$.abstract'), NULL),
        volume   : coalesce(json_extract(w.doc, '$.volume'), NULL),
        issue    : coalesce(json_extract(w.doc, '$.issue'), NULL),
        first_page : coalesce(json_extract(w.doc, '$.first_page'), NULL),
        last_page  : coalesce(json_extract(w.doc, '$.last_page'), NULL),

        abstract_inverted_index :
            coalesce(json_extract(w.doc, '$.abstract_inverted_index'), '{}')::MAP(VARCHAR, INT[]),

        -- 逐条补全 topics 元素
        topics :
            list_transform(
                coalesce(json_extract(w.doc, '$.topics[*]'), []::JSON[]),
                x -> {
                    id          : json_extract(x, '$.id')::BIGINT,          -- 缺 key -> NULL
                    score       : json_extract(x, '$.score')::DOUBLE,       -- 缺 key -> NULL
                    display_name: json_extract(x, '$.display_name')         -- 缺 key -> NULL
                }::STRUCT(id BIGINT, score DOUBLE, display_name VARCHAR)
            ),

        -- 逐条补全 authorships 元素
        authorships :
            list_transform(
                coalesce(json_extract(w.doc, '$.authorships[*]'), []::JSON[]),
                x -> {
                    author_position : json_extract(x, '$.author_position'),      -- 缺 key -> NULL
                    author : {
                        id           : json_extract(x, '$.author.id')::BIGINT,    -- 缺 key -> NULL
                        display_name : json_extract(x, '$.author.display_name')   -- 缺 key -> NULL
                    }::STRUCT(id BIGINT, display_name VARCHAR),
                    institution : {
                        id           : json_extract(x, '$.institution.id')::BIGINT,    -- 缺 key -> NULL
                        display_name : json_extract(x, '$.institution.display_name')   -- 缺 key -> NULL
                    }::STRUCT(id BIGINT, display_name VARCHAR)
                }::STRUCT(
                    author_position VARCHAR,
                    author STRUCT(id BIGINT, display_name VARCHAR),
                    institution STRUCT(id BIGINT, display_name VARCHAR)
                )
            )
    } AS doc
FROM work_doc w;