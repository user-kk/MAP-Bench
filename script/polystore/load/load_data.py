#!/usr/bin/env python3
"""
python load_data.py
"""
from pathlib import Path
import os,json,csv,sys,subprocess,argparse,time
from typing import Set
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.context import get_context

# --------------- 配置 ---------------
HOST = '127.0.0.1'
DB_NAME = 'openalex_middle'

# 要求
# DATA_ROOT 与 CONTAINER_DATA_ROOT 对应
# TMP_ROOT 与 CONTAINER_TMP_ROOT 对应
DATA_ROOT = '/openalex_middle'   # 当前主机内 csv 根目录 /tmp/polystore/OpenAlex_mini_new
CONTAINER_DATA_ROOT = "/openalex_middle"  # 容器内csv挂载路径
TMP_ROOT = '/tmp/polystore' # 当前主机内临时文件生成目录
CONTAINER_TMP_ROOT = '/tmp/polystore' # 容器内临时文件挂载目录

DIM = 384  # 固定向量维度


# csv → 表名
FILE2TABLE = {
    'sorted_authors.csv': 'author',
    'works.csv': 'work',
    'topics.csv': 'topic',
    'institutions.csv': 'institution',
    'institutions_geo.csv': 'institution_geo'
}

# csv -> 集合名
DOC_FILES = {                 
    'authors_doc.csv': 'author_doc',
    'works_doc.csv': 'work_doc'
}


# 顶点 CSV → JSONL 映射：{label: (csv_path, jsonl_path)}
VERTEX_CSV_JSONL = {
    "author_v": (
        f"{DATA_ROOT}/graph/vertices/author_v.csv",
        f"{TMP_ROOT}/author_v.jsonl"
    ),
    "work_v": (
        f"{DATA_ROOT}/graph/vertices/work_v.csv",
        f"{TMP_ROOT}/work_v.jsonl"
    ),
    "topic_v": (
        f"{DATA_ROOT}/graph/vertices/topic_v.csv",
        f"{TMP_ROOT}/topic_v.jsonl"
    ),
}

# 边 CSV → JSONL 映射：{rel_name: (csv_path, jsonl_path)}
EDGE_CSV_JSONL = {
    "work_referenced_work_e": (
        f"{DATA_ROOT}/graph/edges/work_referenced_work_e.csv",
        f"{TMP_ROOT}/work_referenced_work_e.jsonl"
    ),
    "work_topic_e": (
        f"{DATA_ROOT}/graph/edges/work_topic_e.csv",
        f"{TMP_ROOT}/work_topic_e.jsonl"
    ),
    "work_author_e": (
        f"{DATA_ROOT}/graph/edges/work_author_e.csv",
        f"{TMP_ROOT}/work_author_e.jsonl"
    ),
    "author_author_e": (
        f"{DATA_ROOT}/graph/edges/author_author_e.csv",
        f"{TMP_ROOT}/author_author_e.jsonl"
    ),
}


# vector CSV → collection 名称映射
VECTOR_CSV_JSONL = {
    'topic_vec':(
        f"/openalex_384/topics_vector_384.csv"
    ),
    'work_vec':(
        f"/openalex_384/works_m_vector384.csv"
    )
}


# ------------------------------------

def pg_build_and_load(ctx):
    cur = ctx.pg_cursor
    conn = ctx._pg_conn

    cur.execute("SET search_path TO public")
    conn.commit()
    
    # ---------- 1. 建表 DDL ----------
    CREATE_SQL = {
        'author': """
            CREATE TABLE IF NOT EXISTS author (
                id bigint primary key,
                display_name text,
                works_count integer,
                cited_by_count integer,
                last_known_institution text,
                works_api_url text,
                updated_date timestamp without time zone,
                institution_id bigint
            );
        """,
        'work': """
            CREATE TABLE IF NOT EXISTS work (
                id bigint primary key,
                doi text,
                title text,
                display_name text,
                publication_year integer,
                publication_date text,
                type text,
                cited_by_count integer,
                is_retracted boolean,
                is_paratext boolean,
                cited_by_api_url text,
                language text
            );
        """,
        'topic': """
            CREATE TABLE IF NOT EXISTS topic (
                id bigint primary key,
                display_name text,
                subfield_id text,
                subfield_display_name text,
                field_id text,
                field_display_name text,
                domain_id text,
                domain_display_name text,
                description text,
                keywords text,
                works_api_url text,
                wikipedia_id text,
                works_count integer,
                cited_by_count integer,
                updated_date timestamp without time zone
            );
        """,
        'institution': """
            CREATE TABLE IF NOT EXISTS institution (
                id bigint primary key,
                ror text,
                display_name text,
                country_code text,
                type text,
                homepage_url text,
                image_url text,
                image_thumbnail_url text,
                display_name_acronyms json,
                display_name_alternatives json,
                works_count integer,
                cited_by_count integer,
                works_api_url text,
                updated_date timestamp without time zone
            );
        """,
        'institution_geo': """
            CREATE TABLE IF NOT EXISTS institution_geo (
                institution_id bigint primary key,
                city text,
                geonames_city_id text,
                region text,
                country_code text,
                country text,
                latitude real,
                longitude real
            );
        """
    }


    COPY_STMT = {
        'author':
            "COPY author(id,display_name,works_count,cited_by_count,last_known_institution,works_api_url,updated_date,institution_id) "
            "FROM '{path}' WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'utf8')",
        'work':
            "COPY work(id,doi,title,display_name,publication_year,publication_date,type,cited_by_count,is_retracted,is_paratext,cited_by_api_url,language) "
            "FROM '{path}' WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'utf8')",
        'topic':
            "COPY topic(id,display_name,subfield_id,subfield_display_name,field_id,field_display_name,domain_id,domain_display_name,description,keywords,works_api_url,wikipedia_id,works_count,cited_by_count,updated_date) "
            "FROM '{path}' WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'utf8')",
        'institution':
            "COPY institution(id,ror,display_name,country_code,type,homepage_url,image_url,image_thumbnail_url,display_name_acronyms,display_name_alternatives,works_count,cited_by_count,works_api_url,updated_date) "
            "FROM '{path}' WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'utf8')",
        'institution_geo':
            "COPY institution_geo(institution_id,city,geonames_city_id,region,country_code,country,latitude,longitude) "
            "FROM '{path}' WITH (FORMAT csv, HEADER true, NULL '', ENCODING 'utf8')"
    }
    
    # 3.1 建表
    for ddl in CREATE_SQL.values():
        cur.execute(ddl)
    print('==> PostgreSQL 建表完成')

    # 3.3 COPY 导数据
    for csv_file, tbl in FILE2TABLE.items():
        csv_abs = Path(DATA_ROOT) / 'csv-files' / csv_file
        if not csv_abs.exists():
            print(f'[WARN] {csv_abs} 不存在，跳过')
            continue
        # COPY 必须使用容器内路径
        container_path = CONTAINER_DATA_ROOT + '/csv-files/' + csv_file
        stmt = COPY_STMT[tbl].format(path=container_path)
        print(f'---- 正在 COPY {csv_file} -> {tbl}')
        cur.execute(stmt)
        conn.commit()
        print(f'==> {csv_file} 导入完成')

    conn.commit()
    
    # 建立索引
    cur.execute('CREATE INDEX inst_id_index on author(institution_id);')
    cur.execute('CREATE INDEX author_name_index on author(display_name);')
    print('==> PostgreSQL 全部导入完成')

def mongo_doc_import(ctx):
    """文档 CSV -> MongoDB，第二列 JSON 解析嵌套"""
    csv.field_size_limit(sys.maxsize)
    for csv_name, coll_name in DOC_FILES.items():
        path = os.path.join(DATA_ROOT, 'document', csv_name)
        if not os.path.exists(path):
            print(f'[WARN] {path} 不存在，跳过')
            continue
        col = ctx.mongo_db[coll_name]
        col.drop()                      
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)    
            bulk = []
            for r in reader:
                doc = {
                    '_id': int(r['id']),
                    'doc': json.loads(r['doc'] or '{}')
                }
                if coll_name == 'author_doc':              
                    doc['doi'] = r.get('doi')
                bulk.append(doc)
                if len(bulk) == 10000:
                    col.insert_many(bulk, ordered=False)
                    bulk.clear()
            if bulk:
                col.insert_many(bulk, ordered=False)
        
        print(f'==> {csv_name} -> {coll_name} 导入完成，总数 {col.estimated_document_count()}')
        if coll_name == 'author_doc':
            col.create_index([("doc.display_name_alternatives", 1)])
            print(f'==> 为 {coll_name} 创建索引: doc.display_name_alternatives')
        if coll_name == 'work_doc':
            col.create_index([("doc.topics.display_name", 'hashed')])
            print(f'==> 为 {coll_name} 创建索引: doc.topics.display_name : hashed')

def _csv_vertex_to_jsonl(csv_path: str, jsonl_path: str, batch_size=100_000):
    """转换顶点 CSV 到 JSONL"""
    csv_path = Path(csv_path)
    jsonl_path = Path(jsonl_path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    row_cnt = 0
    with csv_path.open(newline="", encoding="utf-8") as fin, \
         jsonl_path.open("w", encoding="utf-8") as fout:

        reader = csv.DictReader(fin)
        batch = []

        for row in reader:
            try:
                node_id = int(row["id"])
            except (ValueError, KeyError):
                print(f"[WARN] 顶点行缺失有效 id，跳过: {row}", file=sys.stderr)
                continue

            # 解析 properties 字段
            try:
                props = json.loads(row.get("properties", "{}"))
            except json.JSONDecodeError:
                props = {}

            # 构建新记录：保留 id + 展开 properties
            new_rec = {"id": node_id}
            new_rec.update(props)

            # 保留其他非 id/properties 字段（如有）
            for k, v in row.items():
                if k not in {"id", "properties"}:
                    new_rec[k] = v

            batch.append(new_rec)

            if len(batch) >= batch_size:
                fout.write("".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in batch))
                row_cnt += len(batch)
                batch.clear()

        if batch:
            fout.write("".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in batch))
            row_cnt += len(batch)

    print(f"✅ 顶点转换完成: {csv_path} → {jsonl_path} ({row_cnt} 条)")

def _csv_edge_to_jsonl(csv_path: str, jsonl_path: str, batch_size=100_000):
    """转换边 CSV 到 JSONL"""
    csv_path = Path(csv_path)
    jsonl_path = Path(jsonl_path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    row_cnt = 0
    with csv_path.open(newline="", encoding="utf-8") as fin, \
         jsonl_path.open("w", encoding="utf-8") as fout:

        reader = csv.DictReader(fin)
        batch = []

        for row in reader:
            try:
                start_id = int(row["startid"])
                end_id = int(row["endid"])
            except (ValueError, KeyError):
                print(f"[WARN] 边行缺失 startid/endid，跳过: {row}", file=sys.stderr)
                continue

            # 解析 properties
            try:
                props = json.loads(row.get("properties", "{}"))
            except json.JSONDecodeError:
                props = {}

            new_rec = {"start_id": start_id, "end_id": end_id}
            new_rec.update(props)

            # 保留其他字段（如 author_position 等）
            for k, v in row.items():
                if k not in {"startid", "endid", "properties"}:
                    new_rec[k] = v

            batch.append(new_rec)

            if len(batch) >= batch_size:
                fout.write("".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in batch))
                row_cnt += len(batch)
                batch.clear()

        if batch:
            fout.write("".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in batch))
            row_cnt += len(batch)

    print(f"✅ 边转换完成: {csv_path} → {jsonl_path} ({row_cnt} 条)")

def neo4j_import_graph(ctx, force_convert=False,slice_lines=500_000):
    """
    自动将 CSV 转为 JSONL，并通过 APOC 导入 Neo4j。
    
    Args:
        ctx: 包含 neo4j_session 的上下文对象
        force_convert: 是否强制重新生成 JSONL（即使已存在）
    """
    session = ctx.neo4j_session
    csv.field_size_limit(sys.maxsize)

    # -------------------------------
    # Step 1: 转换顶点 CSV → JSONL
    # -------------------------------
    print("==> 正在转换顶点 CSV 为 JSONL...")
    for label, (csv_path, jsonl_path) in VERTEX_CSV_JSONL.items():
        if not os.path.exists(csv_path):
            print(f"[SKIP] 顶点 CSV 不存在: {csv_path}")
            continue
        if not force_convert and os.path.exists(jsonl_path):
            print(f"[SKIP] JSONL 已存在（跳过转换）: {jsonl_path}")
        else:
            _csv_vertex_to_jsonl(csv_path, jsonl_path)

    # -------------------------------
    # Step 2: 转换边 CSV → JSONL
    # -------------------------------
    print("==> 正在转换边 CSV 为 JSONL...")
    for rel_name, (csv_path, jsonl_path) in EDGE_CSV_JSONL.items():
        if not os.path.exists(csv_path):
            print(f"[SKIP] 边 CSV 不存在: {csv_path}")
            continue
        if not force_convert and os.path.exists(jsonl_path):
            print(f"[SKIP] JSONL 已存在（跳过转换）: {jsonl_path}")
        else:
            _csv_edge_to_jsonl(csv_path, jsonl_path)

    # -------------------------------
    # Step 3: 通过 APOC 导入 Neo4j
    # -------------------------------
    print("==> 开始通过 APOC 批量导入图数据到 Neo4j...")
    

    # 顶点导入语句
    vertex_queries = [
        f'''
        CALL apoc.periodic.iterate(
          'CALL apoc.load.json("file:///author_v.jsonl") YIELD value RETURN value',
          'CREATE (a:author_v {{
             id: value.id,
             display_name: value.display_name,
             works_count: toInteger(value.works_count),
             cited_by_count: toInteger(value.cited_by_count)
           }})',
          {{batchSize: 1000000, parallel: true}}
        )
        ''',

        f'''
        CALL apoc.periodic.iterate(
          'CALL apoc.load.json("file:///work_v.jsonl") YIELD value RETURN value',
          'CREATE (w:work_v {{
             id: value.id,
             title: value.title,
             publication_year: toInteger(value.publication_year),
             publication_date: value.publication_date,
             type: value.type,
             cited_by_count: toInteger(value.cited_by_count),
             is_retracted: value.is_retracted,
             is_paratext: value.is_paratext
           }})',
          {{batchSize: 100000, parallel: true}}
        )
        ''',

        f'''
        CALL apoc.periodic.iterate(
          'CALL apoc.load.json("file:///topic_v.jsonl") YIELD value RETURN value',
          'CREATE (t:topic_v {{
             id: value.id,
             display_name: value.display_name,
             keywords: value.keywords,
             works_count: toInteger(value.works_count),
             cited_by_count: toInteger(value.cited_by_count)
           }})',
          {{batchSize: 10000, parallel: true}}
        )
        '''
    ]
    
    for i, query in enumerate(vertex_queries, 1):
        print(f"  执行顶点导入任务 {i}/{len(vertex_queries)} ...")
        session.run(query)
        
    start_time = time.time()
    
    print("==> 正在为顶点 id 建立索引...")
    index_queries = [
        "CREATE INDEX IF NOT EXISTS FOR (a:author_v) ON (a.id);",
        "CREATE INDEX IF NOT EXISTS FOR (w:work_v) ON (w.id);",
        "CREATE INDEX IF NOT EXISTS FOR (t:topic_v) ON (t.id);"
    ]
    for idx_query in index_queries:
        session.run(idx_query)
        
    end_time = time.time()  
    elapsed_time = end_time - start_time
    print(f"==> 索引建立完成，耗时: {elapsed_time:.2f} 秒，开始导入边...")

        # ------- 3.3 边 -------
    def _import_small_edge(jsonl_name, cypher):
        print(f"  直接导入 {jsonl_name}")
        session.run(cypher)

    def _import_big_edge(jsonl_path, cypher_tpl):
        """大边文件：先切片再逐片导，要不然会无响应"""
        jsonl_path = Path(jsonl_path)
        if not jsonl_path.exists():
            print(f"[SKIP] {jsonl_path} 不存在")
            return
        # 切片目录
        slice_dir = jsonl_path.with_suffix('')
        slice_dir.mkdir(exist_ok=True)
        # 如果目录里已有切片且未强制重新切，就跳过
        if not any(slice_dir.iterdir()) or force_convert:
            print(f"  正在切片 {jsonl_path.name} ...")
            subprocess.run([
                'split', '-a', '6', '-d', '-l', str(slice_lines),
                str(jsonl_path),
                str(slice_dir / jsonl_path.stem) + '_'
            ], check=True)
        else:
            print(f"  使用已有切片 {slice_dir}")

        # 逐片导入
        files = sorted(slice_dir.glob('*'))
        total = len(files)
        for idx, chunk in enumerate(files, 1):
            print(f"    切片 {idx:>{len(str(total))}}/{total} : {chunk.name}")
            rel_path = chunk.relative_to(TMP_ROOT) 
            neo4j_path = f"file:///{rel_path}"   
            cypher = cypher_tpl.format(file_path=neo4j_path)
            print(cypher)
            session.run(cypher)  # 通过 $file 传路径

    # 3.3.1 小边
    _import_small_edge(
        "work_referenced_work_e.jsonl",
        '''
        CALL apoc.periodic.iterate(
          'CALL apoc.load.json("file:///work_referenced_work_e.jsonl") YIELD value RETURN value',
          'MATCH (w1:work_v {id: value.start_id})
           MATCH (w2:work_v {id: value.end_id})
           CREATE (w1)-[:work_referenced_work_e]->(w2)',
          {batchSize: 50000, parallel: true}
        )
        '''
    )
    _import_small_edge(
        "work_topic_e.jsonl",
        '''
        CALL apoc.periodic.iterate(
          'CALL apoc.load.json("file:///work_topic_e.jsonl") YIELD value RETURN value',
          'MATCH (w:work_v {id: value.start_id})
           MATCH (t:topic_v {id: value.end_id})
           CREATE (w)-[:work_topic_e {score: toFloat(value.score)}]->(t)',
          {batchSize: 50000, parallel: true}
        )
        '''
    )

    # 3.3.2 大边：work_author_e
    _import_big_edge(
        EDGE_CSV_JSONL["work_author_e"][1],
        '''
        CALL apoc.periodic.iterate(
        'CALL apoc.load.json("{file_path}") YIELD value RETURN value',
        'MATCH (w:work_v {{id: value.start_id}})
        MATCH (a:author_v {{id: value.end_id}})
        MERGE (w)-[e:work_author_e]->(a)
            ON CREATE SET e.author_position = value.author_position',
        {{batchSize: 10000, parallel: false}}
        )
        '''
    )

    # 3.3.3 大边：author_author_e
    _import_big_edge(
        EDGE_CSV_JSONL["author_author_e"][1],
        '''
        CALL apoc.periodic.iterate(
        'CALL apoc.load.json("{file_path}") YIELD value RETURN value',
        'MATCH (a1:author_v {{id: value.start_id}})
        MATCH (a2:author_v {{id: value.end_id}})
        WITH a1, a2, value,
                [item IN value.list | toInteger(item.year)]   AS years,
                [item IN value.list | toInteger(item.work_id)] AS work_ids,
                apoc.convert.toJson(value.list)               AS list
        MERGE (a1)-[r:author_author_e]->(a2)
            ON CREATE SET r.cnt = toInteger(value.cnt),
                        r.years = years,
                        r.work_ids = work_ids,
                        r.list = list
        {{batchSize: 10000, parallel: false}}
        )
        '''
    )

    print("==> Neo4j 图数据导入完成！")

def _csv_vec_to_jsonl(csv_path: str, jsonl_path: str, batch_size=100_000):
    """转换向量 CSV 到 JSONL（vec 字段为 Python 列表字符串，如 '[0.1, 0.2, ...]'）"""
    csv_path = Path(csv_path)
    jsonl_path = Path(jsonl_path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    row_cnt = 0
    with csv_path.open(newline="", encoding="utf-8") as fin, \
         jsonl_path.open("w", encoding="utf-8") as fout:

        reader = csv.DictReader(fin)
        batch = []

        for row in reader:
            try:
                # 必须有 id 字段
                id_val = int(row["id"])
            except (ValueError, KeyError) as e:
                print(f"[WARN] 行缺失或无效 id，跳过 (行号 {reader.line_num}): {e}", file=sys.stderr)
                continue

            # 解析 vec 字段：支持 '[...]' 形式的列表字符串
            try:
                vec_str = row.get("vec", "").strip()
                if not vec_str.startswith("[") or not vec_str.endswith("]"):
                    raise ValueError("vec 不是列表格式")
                # 使用 json.loads 更安全；若原数据是 Python repr（如含单引号），可 fallback 到 ast.literal_eval
                try:
                    vec = json.loads(vec_str)
                except json.JSONDecodeError:
                     raise ValueError("vec json格式错误")
            except Exception as e:
                print(f"[WARN] vec 解析失败 (id={id_val}, 行号 {reader.line_num}): {e}", file=sys.stderr)
                continue

            # 构建新记录
            new_rec = {"id": id_val, "vec": vec}

            # 保留其他字段（如 doi 等），但排除原始 id 和 vec
            for k, v in row.items():
                if k not in {"id", "vec"}:
                    new_rec[k] = v

            batch.append(new_rec)

            if len(batch) >= batch_size:
                fout.write("".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in batch))
                row_cnt += len(batch)
                batch.clear()

        if batch:
            fout.write("".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in batch))
            row_cnt += len(batch)

    print(f"✅ 向量转换完成: {csv_path} → {jsonl_path} ({row_cnt} 条)")

def milvus_import_vectors(ctx):
    """
    导入 向量 CSV 到 Milvus（固定维度）
    - topics_vec.csv → topic_vec collection (id INT64, vec FLOAT_VECTOR[DIM])
    - works_vec.csv  → work_vec collection  (id INT64, doi VARCHAR(256), vec FLOAT_VECTOR[DIM])
    """
    
    for collection_name, (csv_path) in VECTOR_CSV_JSONL.items():
        from pymilvus import Collection, CollectionSchema,FieldSchema, DataType, utility
        
        if utility.has_collection(collection_name):
            print(f"[INFO] Milvus 集合 {collection_name} 已存在，跳过创建")
            collection = Collection(collection_name)
        else:
            print(f"[INFO] 正在创建 Milvus 集合: {collection_name}")

            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name="vec", dtype=DataType.FLOAT_VECTOR, dim=DIM)
            ]

            # works_vec 包含 doi 字段
            if collection_name == "work_vec":
                fields.insert(1, FieldSchema(name="doi", dtype=DataType.VARCHAR, max_length=256))

            schema = CollectionSchema(
                fields=fields,
                description=f"OpenAlex {collection_name} ({DIM}-dim vectors)"
            )
            collection = Collection(name=collection_name, schema=schema)

        # 开始分批插入
        
        print(f"==> 开始插入 {collection_name} ...")
        total = 0
        csv.field_size_limit(sys.maxsize)
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            batch_ids, batch_vecs, batch_doi = [], [], []
            for row in reader:
                try:
                    _id = int(row["id"])
                    vec = json.loads(row["vec"])          # [0.1, 0.2, ...]
                except Exception as e:
                    print(f"[WARN] 解析失败，跳过行 {reader.line_num}: {e}")
                    continue

                batch_ids.append(_id)
                batch_vecs.append(vec)
                if collection_name == "work_vec":
                    batch_doi.append(row.get("doi", ""))

                # 每 20 000 条刷一次
                if len(batch_ids) >= 20_000:
                    data = [batch_ids, batch_vecs] if collection_name != "work_vec" \
                           else [batch_ids, batch_doi, batch_vecs]
                    collection.insert(data)
                    total += len(batch_ids)
                    batch_ids, batch_vecs, batch_doi = [], [], []

            # 末尾不足一批
            if batch_ids:
                data = [batch_ids, batch_vecs] if collection_name != "work_vec" \
                       else [batch_ids, batch_doi, batch_vecs]
                collection.insert(data)
                total += len(batch_ids)

        collection.flush()          # 落盘
        print(f"✅ {collection_name} 插入完成，累计 {total} 条向量")
        # 创建索引（HNSW）
        
        if not collection.has_index():          # 防止重复建索引
            start_time = time.time()
            index_params = {
                "index_type": "HNSW",
                "metric_type": "L2",
                "params": {
                    "M": 8,
                    "efConstruction": 64 if collection_name == "work_vec" else 32
                }
            }
            collection.create_index(field_name="vec", index_params=index_params)
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"✅ 为 {collection_name} 创建 L2+HNSW 索引 index_params:{index_params},耗时 {elapsed_time:.2f} 秒")
            

def parse_cli() -> Set[str]:
    """解析命令行，返回要导入的数据库简称集合。"""
    parser = argparse.ArgumentParser(
        description="可选地将数据导入一种或多种下游数据库。"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-a", "--all", action="store_true",
        help="导入所有数据库（默认）"
    )
    # 单个开关
    parser.add_argument("-p", "--pg",      action="store_true", help="导入 PostgreSQL")
    parser.add_argument("-m", "--mongo",   action="store_true", help="导入 MongoDB")
    parser.add_argument("-n", "--neo4j",   action="store_true", help="导入 Neo4j")
    parser.add_argument("-v", "--milvus",  action="store_true", help="导入 Milvus")
    args = parser.parse_args()

    # 如果什么都没选，默认就是 --all
    if not any((args.pg, args.mongo, args.neo4j, args.milvus)):
        args.all = True

    targets = set()
    if args.all:
        targets.update(["pg", "mongo", "neo4j", "milvus"])
    else:
        if args.pg:     targets.add("pg")
        if args.mongo:  targets.add("mongo")
        if args.neo4j:  targets.add("neo4j")
        if args.milvus: targets.add("milvus")
    return targets


if __name__ == "__main__":
    targets = parse_cli()

    ctx = get_context(HOST)
    ctx.create_databases([DB_NAME])
    ctx.use(DB_NAME)

    if "pg"     in targets:  pg_build_and_load(ctx)
    if "mongo"  in targets:  mongo_doc_import(ctx)
    if "neo4j"  in targets:  neo4j_import_graph(ctx)
    if "milvus" in targets:  milvus_import_vectors(ctx)

    ctx.close()