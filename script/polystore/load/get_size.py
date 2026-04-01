#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
from typing import Dict, List
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.context import Context, get_context

# ================= 配置区域 =================
# polystore 连接配置
POLYSTORE_HOST = "127.0.0.1"
POLYSTORE_DB = "mapl"

# 每个数据库要统计的对象列表
POSTGRESQL_TABLES = ['author', 'work', 'topic', 'institution']
MONGODB_COLLECTIONS = ['author_doc', 'work_doc']
MILVUS_COLLECTIONS = ['topic_vec', 'work_vec']
NEO4J_LABELS = ['author_v', 'topic_v', 'work_v', 'author_author_e', 'work_referenced_work_e', 'work_author_e', 'work_topic_e']

# 模型分类定义（用于汇总）
MODEL_CATEGORIES = {
    '关系模型': POSTGRESQL_TABLES,
    '文档模型': MONGODB_COLLECTIONS,
    '向量模型': MILVUS_COLLECTIONS,
    '图模型(估计，按比例分配)': NEO4J_LABELS
}

# 自动生成表顺序字典
def generate_table_order(categories: Dict[str, List[str]]) -> Dict[str, int]:
    """从 MODEL_CATEGORIES 自动生成 TABLE_ORDER 字典"""
    table_order = {}
    order = 1
    for category_tables in categories.values():
        for table_name in category_tables:
            table_order[table_name] = order
            order += 1
    return table_order

TABLE_ORDER = generate_table_order(MODEL_CATEGORIES)
# ===========================================

def format_size(bytes_value: int) -> str:
    """将字节数转换为人类可读格式"""
    if not bytes_value or bytes_value <= 0:
        return "0"
    if bytes_value >= 1073741824:  # GB
        return f"{bytes_value / 1073741824:.2f}"
    elif bytes_value >= 1048576:  # MB
        return f"{bytes_value / 1048576:.1f}"
    elif bytes_value >= 1024:  # KB
        return f"{bytes_value / 1024:.0f}"
    else:
        return f"{bytes_value}"

def get_size_unit(bytes_value: int) -> str:
    """获取大小单位"""
    if not bytes_value or bytes_value <= 0:
        return "bytes"
    if bytes_value >= 1073741824:
        return "GB"
    elif bytes_value >= 1048576:
        return "MB"
    elif bytes_value >= 1024:
        return "KB"
    else:
        return "bytes"

def get_dir_size_in_minio(container_path: str) -> int:
    """在 minio 容器内获取目录大小（字节数）"""
    try:
        # 使用 du -sb 获取字节数，避免单位转换问题
        cmd = f"docker exec milvus-minio du -sb {container_path} 2>/dev/null | cut -f1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output and output.isdigit():
                return int(output)
        return 0
    except Exception as e:
        print(f"    警告: 无法访问 minio 容器路径 {container_path}: {e}")
        return 0

def get_milvus_collection_disk_usage(collection_id: int) -> int:
    """统计 Milvus collection 在 minio 中的总磁盘占用（字节）"""
    total_bytes = 0
    
    # 统计 insert_log 目录大小
    insert_log_path = f"/minio-data/a-bucket/files/insert_log/{collection_id}"
    insert_size = get_dir_size_in_minio(insert_log_path)
    
    # 统计 index_files 目录大小
    index_files_path = f"/minio-data/a-bucket/files/index_files/{collection_id}"
    index_size = get_dir_size_in_minio(index_files_path)
    
    total_bytes = insert_size + index_size
    
    if total_bytes > 0:
        print(f"    磁盘占用: {format_size(total_bytes)} {get_size_unit(total_bytes)}")
    
    return total_bytes

def get_postgresql_stats(ctx) -> List[Dict]:
    """PostgreSQL统计（关系模型）"""
    stats = []
    cursor = ctx.pg_cursor
    
    print("正在统计 PostgreSQL...")
    
    for table in POSTGRESQL_TABLES:
        try:
            # 检查表是否存在
            cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s", (table,))
            if not cursor.fetchone():
                print(f"  ⚠ 表 {table} 不存在")
                continue
            
            # 主表数据
            cursor.execute(f"SELECT pg_relation_size('{table}')")
            main_bytes = cursor.fetchone()[0]
            
            # TOAST表大小
            cursor.execute(f"""
                SELECT pg_relation_size(c.reltoastrelid) 
                FROM pg_class c 
                JOIN pg_namespace n ON n.oid = c.relnamespace 
                WHERE n.nspname = 'public' AND c.relname = '{table}'
            """)
            toast_result = cursor.fetchone()
            toast_bytes = toast_result[0] if toast_result else 0
            
            # 索引
            cursor.execute(f"SELECT pg_indexes_size('{table}')")
            index_bytes = cursor.fetchone()[0]
            
            # 索引数量
            cursor.execute("SELECT COUNT(*) FROM pg_indexes WHERE tablename=%s AND schemaname='public'", (table,))
            index_count = cursor.fetchone()[0]
            
            data_bytes = main_bytes + toast_bytes
            
            stats.append({
                'table_name': table,
                'data_bytes': data_bytes,
                'index_bytes': index_bytes,
                'total_bytes': data_bytes + index_bytes,
                'index_count': index_count,
                'model': '关系模型'
            })
            
            print(f"  ✓ {table}: 数据 {format_size(data_bytes)} {get_size_unit(data_bytes)}, "
                  f"索引 {format_size(index_bytes)} {get_size_unit(index_bytes)}")
            
        except Exception as e:
            print(f"  ✗ {table} 失败: {e}")
    
    return stats

def get_mongodb_stats(ctx) -> List[Dict]:
    """MongoDB统计（文档模型）"""
    stats = []
    db = ctx.mongo_db
    
    print("\n正在统计 MongoDB...")
    
    for coll in MONGODB_COLLECTIONS:
        try:
            if coll not in db.list_collection_names():
                print(f"  ⚠ 集合 {coll} 不存在")
                continue
            
            # 大小统计
            stats_info = db.command("collstats", coll)
            data_bytes = stats_info.get('storageSize', 0)
            index_bytes = stats_info.get('totalIndexSize', 0)
            
            # 索引数量
            index_count = len(stats_info.get('indexSizes', {}))
            
            stats.append({
                'table_name': coll,
                'data_bytes': data_bytes,
                'index_bytes': index_bytes,
                'total_bytes': data_bytes + index_bytes,
                'index_count': index_count,
                'model': '文档模型'
            })
            
            print(f"  ✓ {coll}: 数据 {format_size(data_bytes)} {get_size_unit(data_bytes)}, "
                  f"索引 {format_size(index_bytes)} {get_size_unit(index_bytes)}")
            
        except Exception as e:
            print(f"  ✗ {coll} 失败: {e}")
    
    return stats

def get_milvus_index_file_ids(collection_id: int) -> List[int]:
    """从 etcd 获取指定 collection 的所有索引文件目录 ID"""
    try:
        # 构建 etcdctl 命令，查询该 collection 的所有 segment-index 信息
        cmd = f'docker exec milvus-etcd etcdctl get --prefix "by-dev/meta/segment-index/{collection_id}" --keys-only'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"    警告: 无法从 etcd 获取索引信息: {result.stderr}")
            return []
        
        # 解析输出，提取索引文件目录 ID (路径最后一个部分)
        index_file_ids = set()
        for line in result.stdout.strip().split('\n'):
            if line and 'by-dev/meta/segment-index/' in line:
                # 格式: by-dev/meta/segment-index/{collection_id}/{segment_id}/{field_id}/{index_file_id}
                parts = line.strip().split('/')
                if len(parts) >= 5:
                    index_file_id = int(parts[-1])
                    index_file_ids.add(index_file_id)
        
        return list(index_file_ids)
    except Exception as e:
        print(f"    警告: 获取索引文件目录 ID 失败: {e}")
        return []

def get_milvus_collection_disk_usage(collection_id: int) -> tuple[int, int, int]:
    """统计 Milvus collection 在 minio 中的数据大小和索引大小（字节）
    返回: (数据大小, 索引大小, 总大小)
    """
    total_index_size = 0
    
    # 1. 统计数据大小（insert_log）
    insert_log_path = f"/minio-data/a-bucket/files/insert_log/{collection_id}"
    data_size = get_dir_size_in_minio(insert_log_path)
    
    if data_size > 0:
        print(f"    数据文件: {format_size(data_size)} {get_size_unit(data_size)}")
    
    # 2. 获取所有索引文件目录 ID
    index_file_ids = get_milvus_index_file_ids(collection_id)
    
    # 3. 统计所有索引文件目录的总大小
    if index_file_ids:
        print(f"    发现 {len(index_file_ids)} 个索引文件目录")
        
        for idx_file_id in index_file_ids:
            index_path = f"/minio-data/a-bucket/files/index_files/{idx_file_id}"
            idx_size = get_dir_size_in_minio(index_path)
            
            if idx_size > 0:
                total_index_size += idx_size
                print(f"      {idx_file_id}: {format_size(idx_size)} {get_size_unit(idx_size)}")
    
    total_size = data_size + total_index_size
    
    if total_size > 0:
        print(f"    总计: {format_size(total_size)} {get_size_unit(total_size)}")
    
    return data_size, total_index_size, total_size

def get_milvus_stats(ctx) -> List[Dict]:
    """Milvus统计（向量模型）- 通过 docker exec 获取真实磁盘占用"""
    stats = []
    
    print("\n正在统计 Milvus...")
    
    for coll_name in MILVUS_COLLECTIONS:
        try:
            if not ctx.milvus_util.has_collection(coll_name):
                print(f"  ⚠ 集合 {coll_name} 不存在")
                continue
            
            # 获取 Collection 对象和描述信息
            coll = ctx.get_milvus_collection(coll_name)
            coll_info = coll.describe()
            collection_id = coll_info['collection_id']
            
            print(f"  → {coll_name} (ID: {collection_id})")
            
            # 获取数据和索引的磁盘占用
            data_bytes, index_bytes, total_bytes = get_milvus_collection_disk_usage(collection_id)
            
            index_count = 2 # 都是两个索引 一个id,一个向量索引
            
            stats.append({
                    'table_name': coll_name,
                    'data_bytes': data_bytes,
                    'index_bytes': index_bytes,
                    'total_bytes': total_bytes,
                    'index_count': index_count,
                    'model': '向量模型'
                })
                
        except Exception as e:
            print(f"  ✗ {coll_name} 失败: {e}")
            import traceback
            traceback.print_exc()
    
    return stats

def get_neo4j_disk_usage() -> tuple[int, int, int, Dict[str, int]]:
    """通过 docker du 精确获取 Neo4j 磁盘占用（字节）
    返回: (数据文件总大小, 索引文件总大小, 总大小, 详细分类)
    
    基于实际文件结构：
    - 节点数据: neostore.nodestore.db* 文件
    - 关系数据: neostore.relationshipstore.db* 文件
    - 属性数据: neostore.propertystore.db* 文件（包含数组、字符串、索引）
    - 标签/类型数据: neostore.labeltokenstore.db*, neostore.relationshiptypestore.db*
    - 关系分组数据: neostore.relationshipgroupstore.db*
    - 统计信息: neostore.counts.db
    - 其他: neostore, neostore.indexstats.db, neostore.schemastore.db*
    - 索引文件: schema/index/ 目录（包含 range, token-lookup 等索引类型）
    """
    total_bytes = 0
    index_bytes = 0
    detail = {}
    
    try:
        # 1. 获取总大小（整个数据目录，最可靠）
        cmd = "docker exec neo4j du -sb /data/databases/neo4j 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            total_bytes = int(result.stdout.strip().split()[0])
        else:
            print(f"  ⚠ 无法获取 Neo4j 总大小: {result.stderr}")
            return 0, 0, 0, detail
        
        # 2. 获取索引文件大小（schema/index 目录及其所有子目录）
        cmd = "docker exec neo4j du -sb /data/databases/neo4j/schema/index 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            index_bytes = int(result.stdout.strip().split()[0])
        else:
            index_bytes = 0
            print(f"    索引文件: 0 bytes (无法访问)")
        
        # 3. 统计各类数据文件大小
        base_path = "/data/databases/neo4j"
        
        # 节点数据
        node_files = [
            "neostore.nodestore.db",
            "neostore.nodestore.db.id",
            "neostore.nodestore.db.labels"
        ]
        detail['nodes'] = sum(get_file_size(base_path, f) for f in node_files)
        
        # 关系数据
        rel_files = [
            "neostore.relationshipstore.db",
            "neostore.relationshipstore.db.id"
        ]
        detail['relationships'] = sum(get_file_size(base_path, f) for f in rel_files)
        
        # 属性数据（包括数组、字符串、索引键）
        prop_files = [
            "neostore.propertystore.db",
            "neostore.propertystore.db.id",
            "neostore.propertystore.db.arrays",
            "neostore.propertystore.db.arrays.id",
            "neostore.propertystore.db.strings",
            "neostore.propertystore.db.strings.id",
            "neostore.propertystore.db.index",
            "neostore.propertystore.db.index.id",
            "neostore.propertystore.db.index.keys",
            "neostore.propertystore.db.index.keys.id"
        ]
        detail['properties'] = sum(get_file_size(base_path, f) for f in prop_files)
        
        # 标签/类型数据
        token_files = [
            "neostore.labeltokenstore.db",
            "neostore.labeltokenstore.db.id",
            "neostore.labeltokenstore.db.names",
            "neostore.labeltokenstore.db.names.id",
            "neostore.relationshiptypestore.db",
            "neostore.relationshiptypestore.db.id",
            "neostore.relationshiptypestore.db.names",
            "neostore.relationshiptypestore.db.names.id"
        ]
        detail['labels'] = sum(get_file_size(base_path, f) for f in token_files)
        
        # 关系分组数据
        group_files = [
            "neostore.relationshipgroupstore.db",
            "neostore.relationshipgroupstore.db.id",
            "neostore.relationshipgroupstore.degrees.db"
        ]
        detail['groups'] = sum(get_file_size(base_path, f) for f in group_files)
        
        # 统计信息
        detail['counts'] = get_file_size(base_path, "neostore.counts.db")
        
        # 其他文件（包括主文件、索引统计、schema存储）
        other_files = [
            "neostore",
            "neostore.indexstats.db",
            "neostore.schemastore.db",
            "neostore.schemastore.db.id"
        ]
        detail['other'] = sum(get_file_size(base_path, f) for f in other_files)
        
        # 计算数据文件总大小（所有数据相关文件）
        data_bytes = sum(detail.values())
        
        # 打印详细分类（便于验证）
        print(f"    节点数据:     {format_size(detail['nodes'])} {get_size_unit(detail['nodes'])}")
        print(f"    关系数据:     {format_size(detail['relationships'])} {get_size_unit(detail['relationships'])}")
        print(f"    属性数据:     {format_size(detail['properties'])} {get_size_unit(detail['properties'])}")
        print(f"    标签数据:     {format_size(detail['labels'])} {get_size_unit(detail['labels'])}")
        print(f"    分组数据:     {format_size(detail['groups'])} {get_size_unit(detail['groups'])}")
        print(f"    统计信息:     {format_size(detail['counts'])} {get_size_unit(detail['counts'])}")
        print(f"    其他文件:     {format_size(detail['other'])} {get_size_unit(detail['other'])}")
        print(f"    数据文件总计: {format_size(data_bytes)} {get_size_unit(data_bytes)}")
        print(f"    索引文件总计: {format_size(index_bytes)} {get_size_unit(index_bytes)}")
        print(f"    数据库总计:   {format_size(total_bytes)} {get_size_unit(total_bytes)}")
        
    except Exception as e:
        print(f"  ⚠ 获取 Neo4j 磁盘大小失败: {e}")
        return 0, 0, 0, detail
    
    return data_bytes, index_bytes, total_bytes, detail

def get_file_size(base_dir: str, filename: str) -> int:
    """获取单个文件大小（字节），如果文件不存在返回0"""
    try:
        cmd = f"docker exec neo4j du -sb {base_dir}/{filename} 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return int(result.stdout.strip().split()[0])
        return 0
    except:
        return 0

def get_neo4j_stats(ctx) -> List[Dict]:
    """Neo4j统计（图模型）- 使用APOC获取精确数量 + Docker du获取精确总大小
    磁盘占用按实体数量比例分配（估算）
    """
    stats = []
    
    print("\n正在统计 Neo4j...")
    
    # 1. 获取整体磁盘占用
    data_bytes, index_bytes, total_bytes, _ = get_neo4j_disk_usage()
    
    with ctx.neo4j_session as session:
        try:
            # 检查 APOC
            result = session.run("RETURN apoc.version() as version").data()
            apoc_available = len(result) > 0
        except:
            apoc_available = False
        
        if not apoc_available:
            print("  ⚠ APOC 不可用，跳过统计")
            return stats
        
        print("  → 使用 APOC 获取元数据（磁盘占用将按数量比例估算）")
        
        # 2. 获取元数据
        result = session.run("""
            CALL apoc.meta.stats() YIELD labels, relTypesCount, nodeCount, relCount
            RETURN labels, relTypesCount, nodeCount, relCount
        """).data()
        
        if not result:
            return stats
            
        meta = result[0]
        labels_stats = meta.get('labels', {})
        rel_stats = meta.get('relTypesCount', {})
        total_nodes = meta.get('nodeCount', 0)
        total_rels = meta.get('relCount', 0)
        
        print(f"    总节点数: {total_nodes:,} | 总关系数: {total_rels:,}")
        
        # 3. 获取实际索引数量
        try:
            indexes_result = session.run("SHOW INDEXES").data()
            total_index_count = len(indexes_result)
            print(f"    总索引数: {total_index_count}")
        except:
            total_index_count = 0
        
        # 4. 计算各标签/关系的磁盘占用（按比例分配）
        stats = []
        
        # 统计节点（仅包含在配置中的标签）
        node_stats = []
        total_configured_nodes = 0
        
        for label in NEO4J_LABELS:
            if label.endswith('_v'):  # 节点标签
                node_count = labels_stats.get(label, 0)
                if node_count > 0:
                    node_stats.append({
                        'table_name': label,
                        'count': node_count,
                        'entity_type': '节点'
                    })
                    total_configured_nodes += node_count
        
        # 统计关系（仅包含在配置中的关系类型）
        rel_stats_list = []
        total_configured_rels = 0
        
        for rel_type in NEO4J_LABELS:
            if rel_type.endswith('_e'):  # 关系类型
                rel_count = 0
                for key, count in rel_stats.items():
                    if rel_type in key:
                        rel_count = count
                        break
                
                if rel_count > 0:
                    rel_stats_list.append({
                        'table_name': rel_type,
                        'count': rel_count,
                        'entity_type': '关系'
                    })
                    total_configured_rels += rel_count
        
        # 计算比例并分配磁盘空间
        if total_configured_nodes > 0:
            node_data_per_entity = data_bytes * (total_nodes / (total_nodes + total_rels)) / total_configured_nodes
            node_index_per_entity = index_bytes * (total_nodes / (total_nodes + total_rels)) / total_configured_nodes
        else:
            node_data_per_entity = 0
            node_index_per_entity = 0
        
        if total_configured_rels > 0:
            rel_data_per_entity = data_bytes * (total_rels / (total_nodes + total_rels)) / total_configured_rels
            rel_index_per_entity = index_bytes * (total_rels / (total_nodes + total_rels)) / total_configured_rels
        else:
            rel_data_per_entity = 0
            rel_index_per_entity = 0
        
        # 为每个节点标签创建统计项
        for node in node_stats:
            count = node['count']
            table_data_bytes = int(node_data_per_entity * count)
            table_index_bytes = int(node_index_per_entity * count)
            table_total_bytes = table_data_bytes + table_index_bytes
            
            stats.append({
                'table_name': node['table_name'],
                'data_bytes': table_data_bytes,
                'index_bytes': table_index_bytes,
                'total_bytes': table_total_bytes,
                'index_count': 1,  # 就id有索引
                'model': '图模型',
                'entity_type': '节点',
                'row_count': count,
                'is_estimated': True  # 标记为估算值
            })
            
            print(f"    节点 {node['table_name']}: {count:,} 条 (数据: {format_size(table_data_bytes)}, 索引: {format_size(table_index_bytes)})")
        
        # 为每个关系类型创建统计项
        for rel in rel_stats_list:
            count = rel['count']
            table_data_bytes = int(rel_data_per_entity * count)
            table_index_bytes = int(rel_index_per_entity * count)
            table_total_bytes = table_data_bytes + table_index_bytes
            
            stats.append({
                'table_name': rel['table_name'],
                'data_bytes': table_data_bytes,
                'index_bytes': table_index_bytes,
                'total_bytes': table_total_bytes,
                'index_count': 0,
                'model': '图模型',
                'entity_type': '关系',
                'row_count': count,
                'is_estimated': True  # 标记为估算值
            })
            
            print(f"    关系 {rel['table_name']}: {count:,} 条 (数据: {format_size(table_data_bytes)}, 索引: {format_size(table_index_bytes)})")
        
    return stats

def sort_by_custom_order(stats: List[Dict]) -> List[Dict]:
    """按照 TABLE_ORDER 定义的顺序排序"""
    for row in stats:
        row['sort_order'] = TABLE_ORDER.get(row['table_name'], 999)
    return sorted(stats, key=lambda x: x['sort_order'])

def categorize_tables(stats: List[Dict]) -> Dict[str, List[Dict]]:
    """按模型分类表统计信息"""
    categorized = {category: [] for category in MODEL_CATEGORIES.keys()}
    
    for row in stats:
        table_name = row['table_name']
        for category, tables in MODEL_CATEGORIES.items():
            if table_name in tables:
                categorized[category].append(row)
                break
    
    return categorized

def print_summary(all_stats: List[Dict], category_stats: Dict[str, List[Dict]]):
    """打印统计摘要（按指定顺序）"""
    print("\n" + "=" * 100)
    print("Polystore 多数据库空间统计报告")
    print(f"目标数据库: {POLYSTORE_DB} | 服务器: {POLYSTORE_HOST}")
    print("=" * 100)
    print()
    
    # 按自定义顺序排序
    sorted_stats = sort_by_custom_order(all_stats)
    
    # 打印详细表信息
    print("详细表/集合统计信息:")
    print("-" * 100)
    print(f"{'顺序':<4} {'名称':<25} {'数据大小':<12} {'索引大小':<12} {'总占用':<12} {'索引数':<6} {'备注'}")
    print("-" * 100)
    
    for row in sorted_stats:
        sort_order = TABLE_ORDER.get(row['table_name'], 'N/A')
        table_name = row['table_name']
        
        # 获取大小值和单位
        data_bytes = row['data_bytes']
        index_bytes = row['index_bytes']
        total_bytes = row['total_bytes']
        
        data_size = format_size(data_bytes)
        index_size = format_size(index_bytes)
        total_size = format_size(total_bytes)
        
        data_unit = get_size_unit(data_bytes)
        index_unit = get_size_unit(index_bytes)
        total_unit = get_size_unit(total_bytes)
        
        index_count = row['index_count']
        note = ""
        
        # 特殊信息
        if row['model'] == '向量模型':
            dim = row.get('dim', 0)
            if dim > 0:
                note = f"维度: {dim}"
        elif row['model'] == '图模型':
            if row.get('row_count', 0) > 0:
                note = f"{row['entity_type']}: {row['row_count']}"
        
        print(f"{sort_order:<4} {table_name:<25} {data_size:>6} {data_unit:<5} {index_size:>6} {index_unit:<5} "
              f"{total_size:>6} {total_unit:<5} {index_count:<6} {note}")
    
    print()
    print("=" * 100)
    print("按模型分类汇总")
    print("=" * 100)
    print()
    
    # 按模型分类汇总
    grand_total_data = 0
    grand_total_index = 0
    grand_total_size = 0
    grand_total_indexes = 0
    
    for category, tables in category_stats.items():
        if not tables:
            continue
            
        print(f"{category}:")
        print("-" * 80)
        
        # 计算该模型总计
        total_data = sum(t['data_bytes'] for t in tables)
        total_index = sum(t['index_bytes'] for t in tables)
        total_size = sum(t['total_bytes'] for t in tables)
        total_indexes = sum(t['index_count'] for t in tables)
        
        # 累加到总计
        grand_total_data += total_data
        grand_total_index += total_index
        grand_total_size += total_size
        grand_total_indexes += total_indexes
        
        # 打印该模型下所有表
        for table in tables:
            sort_order = TABLE_ORDER.get(table['table_name'], 'N/A')
            table_name = table['table_name']
            
            data_size = format_size(table['data_bytes'])
            index_size = format_size(table['index_bytes'])
            index_count = table['index_count']
            
            print(f"  [{sort_order:>2}] {table_name:<23} 数据: {data_size:>6} {get_size_unit(table['data_bytes']):<5} "
                  f"索引: {index_size:>6} {get_size_unit(table['index_bytes']):<5} 索引数: {index_count}")
        
        # 小计
        print(f"  {'-' * 75}")
        print(f"  {'小计':<25} 数据: {format_size(total_data):>6} {get_size_unit(total_data):<5} "
              f"索引: {format_size(total_index):>6} {get_size_unit(total_index):<5} 索引数: {total_indexes}")
        print()
    
    # 打印总计
    print("=" * 100)
    print("Polystore 系统总计")
    print("=" * 100)
    print(f"总数据大小: {format_size(grand_total_data):>6} {get_size_unit(grand_total_data)}")
    print(f"总索引大小: {format_size(grand_total_index):>6} {get_size_unit(grand_total_index)}")
    print(f"总占用空间: {format_size(grand_total_size):>6} {get_size_unit(grand_total_size)}")
    print(f"索引总数: {grand_total_indexes}")
    print()
    print("=" * 100)

def main():
    print("=" * 100)
    print("Polystore 多数据库空间统计工具")
    print(f"目标数据库: {POLYSTORE_DB}")
    print(f"服务器地址: {POLYSTORE_HOST}")
    print("=" * 100)
    
    try:
        ctx = Context(
            host=POLYSTORE_HOST,
            pg_port=30000,
            mongo_port=30001,
            neo4j_port=30003,
            milvus_port=30004,
            pwd="linux123"
        )
        ctx.use(POLYSTORE_DB)
        
        print("\n开始统计各数据库占用...")
        
        # 收集所有统计信息
        all_stats = []
        
        pg_stats = get_postgresql_stats(ctx)
        all_stats.extend(pg_stats)
        print(f"  → 完成 {len(pg_stats)} 个表")
        
        mongo_stats = get_mongodb_stats(ctx)
        all_stats.extend(mongo_stats)
        print(f"  → 完成 {len(mongo_stats)} 个集合")
        
        milvus_stats = get_milvus_stats(ctx)
        all_stats.extend(milvus_stats)
        print(f"  → 完成 {len(milvus_stats)} 个向量集合")
        
        neo4j_stats = get_neo4j_stats(ctx)
        all_stats.extend(neo4j_stats)
        print(f"  → 完成 {len(neo4j_stats)} 个图标签")
        
        # 按模型分类
        category_stats = categorize_tables(all_stats)
        
        # 打印汇总报告
        print_summary(all_stats, category_stats)
        
        ctx.close()
        print("\n统计完成！")
        
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()