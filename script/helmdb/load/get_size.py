#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List

# OpenGauss数据库连接配置
DB_CONF = dict(
    dbname='mapl',
    user='hyh',
    password='Linux123',
    host='127.0.0.1',
    port=9999
)

# 图文件存储目录
GRAPH_DATA_DIR = '/home/hyh/project/HELMDB/gaussdata/mm_graph/'

# 需要特殊处理的图表
GRAPH_TABLES = {
    'author_author_gra',
    'work_author_gra',
    'work_topic_gra',
    'work_work_gra'
}

# 定义模型分类（已删除ag_开头的表，新增图表）
MODEL_CATEGORIES = {
    '关系模型': ['author', 'work', 'topic', 'institution'],
    '文档模型': ['author_doc', 'work_doc'],
    '向量模型': ['topic_vec', 'work_vec'],
    '图模型': [
        'author_v', 'topic_v', 'work_v',
        'author_author_e', 'work_referenced_work_e',
        'work_author_e', 'work_topic_e',
        # 新增图表
        'author_author_gra', 'work_author_gra',
        'work_topic_gra', 'work_work_gra'
    ]
}

def generate_table_order(categories: Dict[str, List[str]]) -> Dict[str, int]:
    """从MODEL_CATEGORIES自动生成TABLE_ORDER字典"""
    table_order = {}
    order = 1
    for category_tables in categories.values():
        for table_name in category_tables:
            table_order[table_name] = order
            order += 1
    return table_order

TABLE_ORDER = generate_table_order(MODEL_CATEGORIES)

def format_size(bytes_value: int) -> str:
    """将字节数转换为人类可读格式"""
    if bytes_value >= 1073741824:  # GB
        return f"{bytes_value / 1073741824:.2f} GB"
    elif bytes_value >= 1048576:  # MB
        return f"{bytes_value / 1048576:.2f} MB"
    elif bytes_value >= 1024:  # KB
        return f"{bytes_value / 1024:.2f} kB"
    elif bytes_value > 0:  # bytes
        return f"{bytes_value} bytes"
    else:
        return "0 bytes"

def get_graph_oid(conn, table_name: str) -> int:
    """获取图表的oid"""
    sql = "SELECT %s::regclass::bigint AS oid"
    with conn.cursor() as cur:
        cur.execute(sql, (table_name,))
        result = cur.fetchone()
        return result[0] if result else None

def get_graph_file_size(dbname: str, table_name: str, oid: int) -> int:
    """从文件系统获取图文件大小（字节）"""
    if not os.path.exists(GRAPH_DATA_DIR):
        print(f"警告: 图数据目录不存在: {GRAPH_DATA_DIR}")
        return 0
    
    # 文件名格式：数据库名_图oid.graph
    filename = f"{dbname}_{oid}.graph"
    file_path = os.path.join(GRAPH_DATA_DIR, filename)
    
    if os.path.exists(file_path):
        return os.path.getsize(file_path)
    else:
        # 尝试模糊匹配
        pattern = os.path.join(GRAPH_DATA_DIR, f"{dbname}_*{oid}.graph")
        matching_files = glob.glob(pattern)
        if matching_files:
            return os.path.getsize(matching_files[0])
        else:
            print(f"警告: 未找到图文件 {file_path}")
            return 0

def get_table_stats_with_graph(conn) -> List[Dict]:
    """获取所有表的统计信息（特殊处理图表）"""
    # 查询所有表（包括图表）
    all_tables = list(TABLE_ORDER.keys())
    
    sql = """
    SELECT 
        n.nspname::text AS schema_name,
        c.relname::text AS table_name,
        pg_relation_size(c.oid) + COALESCE(pg_relation_size(c.reltoastrelid), 0) AS data_bytes,
        pg_indexes_size(c.oid) AS index_bytes,
        pg_total_relation_size(c.oid) AS total_bytes,
        (SELECT count(*) FROM pg_indexes i WHERE i.tablename = c.relname AND i.schemaname = n.nspname) AS index_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE (n.nspname = 'public' OR n.nspname = 'academic_net')
      AND c.relkind = 'r'
      AND c.relname NOT LIKE '%%_seq'
      AND c.relname = ANY(%s)
    """
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (all_tables,))
        results = cur.fetchall()
    
    # 特殊处理图表：在查询结果基础上累加文件大小到索引
    for row in results:
        if row['table_name'] in GRAPH_TABLES:
            oid = get_graph_oid(conn, row['table_name'])
            if oid is not None:
                file_size = get_graph_file_size(DB_CONF['dbname'], row['table_name'], oid)
                # 累加到索引大小和总计（文件大小算索引）
                row['index_bytes'] += file_size
                row['total_bytes'] += file_size
                # 手动设置索引计数为1（因为图的索引在pg_indexes中不显示）
                row['index_count'] = 1
    
    return results

def sort_by_custom_order(stats: List[Dict]) -> List[Dict]:
    """按照TABLE_ORDER定义的顺序排序"""
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

def print_summary(stats: List[Dict], category_stats: Dict[str, List[Dict]]):
    """打印统计摘要"""
    print("=" * 100)
    print("OpenGauss 数据库表空间统计报告（含图模型）")
    print("（按指定业务顺序排序）")
    print("=" * 100)
    print()
    
    # 打印详细表信息
    print("详细表统计信息:")
    print("-" * 120)
    print(f"{'顺序':<4} {'Schema':<15} {'Table Name':<25} {'Data Size':<12} {'Index Size':<12} {'Total Size':<12} {'Index Count'} {'备注'}")
    print("-" * 120)
    
    for row in stats:
        sort_order = TABLE_ORDER.get(row['table_name'], 'N/A')
        note = "（图文件）" if row['table_name'] in GRAPH_TABLES else ""
        print(f"{sort_order:<4} {row['schema_name']:<15} {row['table_name']:<25} "
              f"{format_size(row['data_bytes']):<12} {format_size(row['index_bytes']):<12} "
              f"{format_size(row['total_bytes']):<12} {row['index_count']:<11} {note}")
    
    print()
    print("=" * 100)
    print("按模型分类汇总")
    print("=" * 100)
    print()
    
    # 按模型分类汇总
    for category, tables in category_stats.items():
        if not tables:
            continue
            
        print(f"{category}:")
        print("-" * 90)
        
        # 计算总计
        total_data = sum(t['data_bytes'] for t in tables)
        total_index = sum(t['index_bytes'] for t in tables)
        total_size = sum(t['total_bytes'] for t in tables)
        total_indexes = sum(t['index_count'] for t in tables)
        
        # 打印该模型下所有表
        for table in tables:
            sort_order = TABLE_ORDER.get(table['table_name'], 'N/A')
            note = "（图）" if table['table_name'] in GRAPH_TABLES else ""
            print(f"  [{sort_order:>2}] {table['table_name']:<23} "
                  f"数据: {format_size(table['data_bytes']):<12} "
                  f"索引: {format_size(table['index_bytes']):<12} "
                  f"索引数: {table['index_count']}{note}")
        
        print(f"  {'-' * 85}")
        print(f"  {'小计':<25} "
              f"数据: {format_size(total_data):<12} "
              f"索引: {format_size(total_index):<12} "
              f"索引数: {total_indexes}")
        print()
    
    # 计算总计
    total_data = sum(row['data_bytes'] for row in stats)
    total_index = sum(row['index_bytes'] for row in stats)
    total_size = sum(row['total_bytes'] for row in stats)
    total_indexes = sum(row['index_count'] for row in stats)
    
    print("=" * 100)
    print("数据库总计")
    print("=" * 100)
    print(f"总数据大小: {format_size(total_data)}")
    print(f"总索引大小: {format_size(total_index)}")
    print(f"总占用空间: {format_size(total_size)}")
    print(f"索引总数: {total_indexes}")
    print("=" * 100)

def main():
    """主函数"""
    print(f"正在连接数据库 {DB_CONF['host']}:{DB_CONF['port']}/{DB_CONF['dbname']}...")
    print(f"图数据目录: {GRAPH_DATA_DIR}")
    
    # 检查图数据目录
    if not os.path.exists(GRAPH_DATA_DIR):
        print(f"错误: 图数据目录不存在: {GRAPH_DATA_DIR}")
        return
    
    try:
        conn = psycopg2.connect(**DB_CONF)
        print("连接成功！")
        
        # 获取表统计信息（在查询结果基础上处理图表）
        raw_stats = get_table_stats_with_graph(conn)
        
        # 检查缺失表
        found_tables = {row['table_name'] for row in raw_stats}
        expected_tables = set(TABLE_ORDER.keys())
        missing_tables = expected_tables - found_tables
        
        if missing_tables:
            print(f"\n警告: 以下表在数据库中未找到: {', '.join(missing_tables)}")
        
        # 按自定义顺序排序
        stats = sort_by_custom_order(raw_stats)
        
        # 按模型分类
        category_stats = categorize_tables(stats)
        
        # 打印报告
        print_summary(stats, category_stats)
        
    except psycopg2.Error as e:
        print(f"数据库错误: {e}")
    except Exception as e:
        print(f"意外错误: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("\n数据库连接已关闭。")

if __name__ == '__main__':
    main()