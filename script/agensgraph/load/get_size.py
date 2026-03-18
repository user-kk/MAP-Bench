#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import psycopg
from psycopg.rows import dict_row
from typing import Dict, List

# 配置数据库连接参数
DB_CONF = dict(
    dbname='mapl',
    user='agensgraph',
    password='linux123',
    host='127.0.0.1',
    port=5555
)

# 定义模型分类
MODEL_CATEGORIES = {
    '关系模型': ['author', 'work', 'topic', 'institution', 'institution_geo'],
    '文档模型': ['author_doc', 'work_doc'],
    '向量模型': ['topic_vec', 'work_vec'],
    '图模型': [
        'author_v', 'topic_v', 'work_v',
        'author_author_e', 'work_referenced_work_e',
        'work_author_e', 'work_topic_e',
        'ag_vertex', 'ag_edge'
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

# 自动生成排序字典
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

def get_table_stats(conn) -> List[Dict]:
    """获取所有表的统计信息"""
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
      AND c.relname NOT LIKE '%%_seq'  -- 修复：使用双百分号转义
      AND c.relname = ANY(%s)
    """
    
    # 获取所有需要查询的表名列表
    all_tables = list(TABLE_ORDER.keys())
    
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, (all_tables,))
        return cur.fetchall()

def sort_by_custom_order(stats: List[Dict]) -> List[Dict]:
    """按照TABLE_ORDER定义的顺序排序"""
    # 添加排序序号
    for row in stats:
        row['sort_order'] = TABLE_ORDER.get(row['table_name'], 999)
    
    # 按排序序号排序，未定义的排在最后
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
    """打印统计摘要（按指定顺序）"""
    print("=" * 100)
    print("AgensGraph 数据库表空间统计报告")
    print("（按指定业务顺序排序）")
    print("=" * 100)
    print()
    
    # 打印详细表信息（按自定义顺序）
    print("详细表统计信息:")
    print("-" * 100)
    print(f"{'顺序':<4} {'Schema':<12} {'Table Name':<25} {'Data Size':<12} {'Index Size':<12} {'Total Size':<12} {'Index Count'}")
    print("-" * 100)
    
    for row in stats:
        sort_order = TABLE_ORDER.get(row['table_name'], 'N/A')
        print(f"{sort_order:<4} {row['schema_name']:<12} {row['table_name']:<25} "
              f"{format_size(row['data_bytes']):<12} {format_size(row['index_bytes']):<12} "
              f"{format_size(row['total_bytes']):<12} {row['index_count']}")
    
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
        print("-" * 80)
        
        # 计算该模型总计
        total_data = sum(t['data_bytes'] for t in tables)
        total_index = sum(t['index_bytes'] for t in tables)
        total_size = sum(t['total_bytes'] for t in tables)
        total_indexes = sum(t['index_count'] for t in tables)
        
        # 打印该模型下所有表（保持原有顺序）
        for table in tables:
            sort_order = TABLE_ORDER.get(table['table_name'], 'N/A')
            print(f"  [{sort_order:>2}] {table['table_name']:<23} "
                  f"数据: {format_size(table['data_bytes']):<12} "
                  f"索引: {format_size(table['index_bytes']):<12} "
                  f"索引数: {table['index_count']}")
        
        print(f"  {'-' * 75}")
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
    
    try:
        # psycopg3 的连接方式
        conn = psycopg.connect(**DB_CONF)
        print("连接成功！")
        
        # 获取表统计信息
        raw_stats = get_table_stats(conn)
        
        # 检查是否有表被遗漏
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
        
    except psycopg.Error as e:
        print(f"数据库错误: {e}")
    except Exception as e:
        print(f"意外错误: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("\n数据库连接已关闭。")

if __name__ == '__main__':
    main()