#!/usr/bin/env python3
"""
polystore上下文管理工具
Usage:
    from context import Context
    ctx = Context("服务器公网IP")
    ctx.create_databases(["openalex_middle"])
    ctx.use("openalex_middle")
"""
from functools import cached_property
import os, time, random
import pymongo, psycopg, neo4j, pymilvus
from psycopg import sql
from pymilvus import db as milvus_db, utility, Collection
from contextlib import contextmanager

class Context:
    def __init__(self, host="127.0.0.1",
                 pg_port=30000,
                 mongo_port=30001,
                 neo4j_port=30003,
                 milvus_port=30004,
                 user="root",
                 pwd="linux123"):
        self.host        = host
        self.pg_port     = pg_port
        self.mongo_port  = mongo_port
        self.neo4j_port  = neo4j_port
        self.milvus_port = milvus_port
        self.user        = user
        self.pwd         = pwd
        self._current_db = None

    # ---------- 连接 ----------
    @cached_property
    def _pg_conn(self) -> psycopg.Connection:
        """返回 psycopg3 连接（autocommit=True）"""
        return psycopg.connect(
            host=self.host,
            port=self.pg_port,
            user='postgres',
            password=self.pwd,
            dbname="postgres",
            autocommit=True
        )

    @cached_property
    def _mongo_client(self):
        return pymongo.MongoClient(
            f"mongodb://{self.user}:{self.pwd}@"
            f"{self.host}:{self.mongo_port}/admin")

    @cached_property
    def _neo4j_driver(self):
        return neo4j.GraphDatabase.driver(
            f"bolt://{self.host}:{self.neo4j_port}",
            auth=("neo4j", self.pwd))

    @cached_property
    def _milvus_conn(self):
        pymilvus.connections.connect(alias="default",
                                     host=self.host,
                                     port=self.milvus_port)
        return pymilvus

    # ---------- 快捷属性 ----------
    @property
    def pg_cursor(self) -> psycopg.Cursor:
        return self._pg_conn.cursor()

    @property
    def mongo_db(self):
        return self._mongo_client[self._current_db or "test"]

    @property
    def neo4j_session(self):
        return self._neo4j_driver.session(database="neo4j")

    @property
    def milvus_util(self):
        return self._milvus_conn.utility
    
    @property
    def milvus_db(self):
        return milvus_db
    
    def get_milvus_collection(self, name: str):
        """返回已加载的 Milvus collection"""
        coll = Collection(name)
        coll.load()          # 幂等，可重复调用
        return coll

    # ---------- 建库 ----------
    def create_databases(self, db_list=None):
        if not db_list:
            return
        # ---------- PostgreSQL ----------
        with self._pg_conn.cursor() as cur:
            for db in db_list:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (db,)
                )
                if cur.fetchone() is None:
                    cur.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db))
                    )
        print("PostgreSQL ==> 库列表：", db_list)

        # ---------- MongoDB ----------
        for db in db_list:
            self._mongo_client[db].list_collection_names()  # 触发建库
        print("MongoDB ==> 库列表：", db_list)

        # ---------- Milvus ----------
        _ = self._milvus_conn
        for db in db_list:
            if db not in milvus_db.list_database():
                milvus_db.create_database(db)
        print("Milvus ==> 库列表：", db_list)

        # ---------- Neo4j ----------
        _ = self._neo4j_driver
        print("Neo4j ==> 使用逻辑标签划分，无需物理建库")

    # ---------- 切换 ----------
    def use(self, db_name: str):
        if db_name != 'postgres' :
            # 1. 关闭旧连接
            if hasattr(self, "_pg_conn"):
                self._pg_conn.close()
                del self.__dict__["_pg_conn"]   # 强制让 @cached_property 重新计算

            # 2. 重新指向新数据库
            self._pg_conn = psycopg.connect(
                host=self.host, port=self.pg_port,
                user="postgres", password=self.pwd,
                dbname=db_name, autocommit=True
            )

        # MongoDB
        _ = self._mongo_client[db_name]
        # Milvus: 确保连接存在，再切换数据库
        _ = self._milvus_conn
        milvus_db.using_database(db_name)
        self._current_db = db_name
        print(f"全局上下文已切换到 >>> {db_name}")

    # ---------- 关闭 ----------
    def close(self):
        if hasattr(self, "_pg_conn"):
            self._pg_conn.close()
        if hasattr(self, "_mongo_client"):
            self._mongo_client.close()
        if hasattr(self, "_neo4j_driver"):
            self._neo4j_driver.close()
        pymilvus.connections.disconnect("default")

    # --------- 会话级临时集合工具 ---------
    @contextmanager
    def temp_mongo_collection(self, prefix="tmp_w"):
        """创建带会话ID的短命集合，退出时自动删除"""
        session_id = f"{prefix}_{os.getpid()}_{int(time.time()*1e6)}_{random.randint(0,9999)}"
        tmp_col = self.mongo_db[session_id]
        try:
            yield tmp_col
        finally:
            tmp_col.drop()

    @contextmanager
    def temp_neo_nodes(self, label_prefix="tmp"):
        """
        用法:
            with temp_neo_nodes(ctx) as tmp:
                tmp.create_node({"id": 123}, "MyLabel")
        退出时自动删除所有带标签的节点
        """
        session_id = f"{label_prefix}_{os.getpid()}_{int(time.time()*1e6)}_{random.randint(0,9999)}"
        tmp_label = f"__{session_id}"          # 双下划线，避免冲突
        ctx = self

        class _TmpKit:
            def create_node(self, properties: dict):
                """创建带 tmp_label 的节点"""
                ctx.neo4j_session.run(
                    f"CREATE (n:{tmp_label}) SET n = $props",
                    props=properties
                )
            def batch_create_nodes(ctx, props_list: list[dict]):
                """一次 UNWIND 创建 1-N 个节点，带同一会话级标签"""
                session_id = f"__tmp_{os.getpid()}_{int(time.time()*1e6)}"
                cypher = f"""
                UNWIND $rows AS row
                CREATE (n:{tmp_label})
                SET n = row
                """
                ctx.neo4j_session.run(cypher, rows=props_list)
                return session_id 

            def run(self, cypher: str, **parameters):
                """直接跑任意 Cypher，里面可安全引用 tmp_label"""
                return ctx.neo4j_session.run(cypher, **parameters)

        try:
            yield _TmpKit()
        finally:
            # 会话结束：整批删除
            ctx.neo4j_session.run(f"MATCH (n:{tmp_label}) DETACH DELETE n")

    @contextmanager
    def temp_pg_table(self, table_name):
        """
        用法:
            with temp_pg_table(ctx, "tmp_table") as cur:
                cur.execute("CREATE TEMP TABLE tmp_table (...)")
                ...
        退出时临时表自动销毁
        """

        try:
            yield self.pg_cursor
        finally:
            # 会话结束自动 DROP，这里再显式清一次（防御性）
            try:
                self.pg_cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            except Exception:
                pass 


# 线程安全单例（可选）
_ctx = None
def get_context(host="127.0.0.1") -> Context:
    global _ctx
    if _ctx is None:
        _ctx = Context(host)
    return _ctx