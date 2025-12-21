#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import duckdb
import os
from typing import Dict, List

# ================= 配置区域 =================
# DuckDB数据库文件路径配置
DB_CONF = dict(
    db_path='/duckdb_data/openalex_middle.db'
)

# 定义模型分类
MODEL_CATEGORIES = {
    '关系模型': ['author', 'work', 'topic', 'institution', 'institution_geo'],
    '文档模型': ['author_doc', 'work_doc'],
    '向量模型': ['topic_vec', 'work_vec'],
    '图模型': [
        'author_v', 'topic_v', 'work_v',
        'author_author_e', 'work_referenced_work_e',
        'work_author_e', 'work_topic_e'
    ]
}
# ===========================================

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
    if not bytes_value:
        return "0 bytes"
    if bytes_value >= 1073741824:  # GB
        return f"{bytes_value / 1073741824:.2f} GB"
    elif bytes_value >= 1048576:  # MB
        return f"{bytes_value / 1048576:.2f} MB"
    elif bytes_value >= 1024:  # KB
        return f"{bytes_value / 1024:.2f} kB"
    else:
        return f"{bytes_value} bytes"

def get_db_file_size(path: str) -> int:
    """获取数据库文件大小"""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0

def get_block_size(conn) -> int:
    """从数据库获取块大小"""
    try:
        result = conn.execute("SELECT block_size FROM pragma_database_size()").fetchone()
        return result[0] if result else 262144  # 默认256KB
    except:
        return 262144

def get_table_stats(conn, block_size: int) -> List[Dict]:
    """获取所有表的统计信息（基于块统计法 + 系统表索引数）"""
    stats_list = []
    
    # 只获取MODEL_CATEGORIES中定义的表
    all_target_tables = set()
    for tables in MODEL_CATEGORIES.values():
        all_target_tables.update(tables)
    
    print(f"需要统计的表: {len(all_target_tables)}个")
    print("=" * 85)
    print(f"{'表名':<25} {'行数':<12} {'数据块大小':<15} {'索引数':<6}")
    print("=" * 85)
    
    for table_name in all_target_tables:
        # 1. 检查表是否存在
        check_sql = f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='main' AND table_name='{table_name}'"
        exists = conn.execute(check_sql).fetchone()[0]
        if not exists:
            print(f"警告: 表 {table_name} 不存在")
            continue
        
        # 2. 获取行数
        try:
            row_count = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        except:
            row_count = 0
        
        # 3. 获取物理占用大小 (统计唯一的 Block ID)
        data_bytes = 0
        if row_count > 0:
            # 查询 storage_info 统计不重复的 block_id 数量
            sql = f"""
            SELECT count(DISTINCT block_id) 
            FROM pragma_storage_info('{table_name}') 
            WHERE block_id IS NOT NULL;
            """
            block_count = conn.execute(sql).fetchone()[0] or 0
            data_bytes = block_count * block_size
        
        # 4. 从系统表获取索引数量
        index_sql = f"SELECT index_count FROM duckdb_tables() WHERE table_name = '{table_name}'"
        index_result = conn.execute(index_sql).fetchone()
        index_count = index_result[0] if index_result else 0
        
        stats_list.append({
            'table_name': table_name,
            'data_bytes': data_bytes,
            'row_count': row_count,
            'index_count': index_count
        })
        
        print(f"{table_name:<25} {row_count:<12,} {format_size(data_bytes):<15} {index_count:<6}")
    
    print("=" * 85)
    return stats_list

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

def print_summary(stats: List[Dict], category_stats: Dict[str, List[Dict]], file_size: int, block_size: int):
    """打印统计摘要（不显示索引大小）"""
    print("\n" + "=" * 100)
    print("DuckDB 数据库存储统计报告")
    print(f"（基于 Block Count，块大小: {format_size(block_size)}）")
    print("=" * 100)
    print()
    
    # 计算数据库总数据块大小
    total_data_blocks = sum(row['data_bytes'] for row in stats)
    total_rows = sum(row['row_count'] for row in stats)
    
    # 打印详细表信息
    print("详细表统计信息:")
    print("-" * 100)
    print(f"{'顺序':<4} {'Table Name':<28} {'Data Size':<15} {'Rows':<12} {'索引数'}")
    print("-" * 100)
    
    for row in stats:
        sort_order = TABLE_ORDER.get(row['table_name'], 'N/A')
        print(f"{sort_order:<4} {row['table_name']:<28} "
              f"{format_size(row['data_bytes']):<15} {row['row_count']:<12,} {row['index_count']}")
    
    print()
    print("=" * 100)
    print("按模型分类汇总")
    print("=" * 100)
    print()
    
    grand_total_data = 0
    grand_total_rows = 0
    grand_total_indexes = 0
    
    # 按模型分类汇总
    for category, tables in category_stats.items():
        if not tables:
            continue
            
        print(f"{category}:")
        print("-" * 80)
        
        # 计算该模型总计
        cat_data = sum(t['data_bytes'] for t in tables)
        cat_rows = sum(t['row_count'] for t in tables)
        cat_indexes = sum(t['index_count'] for t in tables)
        
        grand_total_data += cat_data
        grand_total_rows += cat_rows
        grand_total_indexes += cat_indexes
        
        # 打印该模型下所有表
        for table in tables:
            sort_order = TABLE_ORDER.get(table['table_name'], 'N/A')
            print(f"  [{sort_order:>2}] {table['table_name']:<26} "
                  f"数据: {format_size(table['data_bytes']):<12} "
                  f"行数: {table['row_count']:,}  "
                  f"索引数: {table['index_count']}")
        
        print(f"  {'-' * 75}")
        print(f"  {'小计':<26} "
              f"数据: {format_size(cat_data):<12} "
              f"行数: {cat_rows:,}  "
              f"索引数: {cat_indexes}")
        print()
    
    # 计算数据库总计
    print("=" * 100)
    print("数据库总计")
    print("=" * 100)
    print(f"总数据块大小:       {format_size(grand_total_data)}")
    print(f"总行数:             {grand_total_rows:,}")
    print(f"总索引数:           {grand_total_indexes}")
    print("-" * 100)
    print(f"实际物理文件大小:   {format_size(file_size)}")
    if file_size > 0:
        ratio = (grand_total_data / file_size) * 100
        print(f"数据块占比:         {ratio:.2f}%")
        if ratio < 50:
            print("提示: 索引和元数据占比较高，建议检查是否需要VACUUM")
    print("=" * 100)

def main():
    """主函数"""
    db_path = DB_CONF['db_path']
    print(f"正在连接 DuckDB 数据库: {db_path} ...")
    
    if not os.path.exists(db_path):
        print("错误: 文件不存在")
        return

    try:
        conn = duckdb.connect(db_path, read_only=True)
        print("连接成功！")
        
        # 动态获取块大小
        block_size = get_block_size(conn)
        print(f"数据库块大小: {format_size(block_size)}\n")
        
        file_size = get_db_file_size(db_path)
        raw_stats = get_table_stats(conn, block_size)
        
        stats = sort_by_custom_order(raw_stats)
        category_stats = categorize_tables(stats)
        print_summary(stats, category_stats, file_size, block_size)
        
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'conn' in locals():
            conn.close()
            print("\n数据库连接已关闭。")

if __name__ == '__main__':
    main()