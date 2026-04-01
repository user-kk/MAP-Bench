#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from arango import ArangoClient, ArangoError
from typing import Dict, List

# ArangoDB连接配置
ARANGO_CONF = dict(
    hosts='http://127.0.0.1:8529',
    username='root',
    password='linux123',
    dbname='mapl'
)

# 定义模型分类（已移除XX_gra集合）
MODEL_CATEGORIES = {
    '关系模型': ['author', 'work', 'topic', 'institution'],
    '文档模型': ['author_doc', 'work_doc'],
    '向量模型': ['topic_vec', 'work_vec'],
    '图模型': [
        'author_v', 'topic_v', 'work_v',
        'author_author_e', 'work_referenced_work_e',
        'work_author_e', 'work_topic_e'
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

def get_collection_stats(db, collection_name: str) -> Dict:
    """获取单个集合的统计信息"""
    try:
        if not db.has_collection(collection_name):
            print(f"警告: 集合 {collection_name} 不存在")
            return None
        
        collection = db.collection(collection_name)
        stats = collection.statistics()
        print((collection_name,stats))
        
        # 从实际输出格式中提取数据
        index_info = stats.get('indexes', {'count': 0, 'size': 0})
        data_size = stats.get('documents_size', 0)
        index_size = index_info.get('size', 0)
        index_count = index_info.get('count', 0)
        
        return {
            'table_name': collection_name,
            'data_bytes': data_size,
            'index_bytes': index_size,
            'total_bytes': data_size + index_size,
            'index_count': index_count
        }
    except ArangoError as e:
        print(f"警告: 获取集合 {collection_name} 统计失败: {e}")
        return None

def get_all_collections_stats(db) -> List[Dict]:
    """获取所有集合信息"""
    results = []
    all_collections = set()
    for tables in MODEL_CATEGORIES.values():
        all_collections.update(tables)
    
    print(f"需要统计的集合: {len(all_collections)}个")
    print("=" * 60)
    
    for collection_name in all_collections:
        stats = get_collection_stats(db, collection_name)
        if stats:
            results.append(stats)
            # 调试输出（不含文档数）
            print(f"集合: {collection_name:<25} 数据: {format_size(stats['data_bytes']):<10} 索引: {format_size(stats['index_bytes'])}")
    
    print("=" * 60)
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
    """打印统计摘要（不含文档数）"""
    print("\n" + "=" * 80)
    print("ArangoDB 数据库集合空间统计报告")
    print("（按指定业务顺序排序）")
    print("=" * 80)
    print()
    
    # 打印详细表信息（已移除文档数列）
    print("详细集合统计信息:")
    print("-" * 80)
    print(f"{'顺序':<4} {'Collection':<25} {'Data Size':<12} {'Index Size':<12} {'Total Size':<12} {'索引数'}")
    print("-" * 80)
    
    for row in stats:
        sort_order = TABLE_ORDER.get(row['table_name'], 'N/A')
        print(f"{sort_order:<4} {row['table_name']:<25} "
              f"{format_size(row['data_bytes']):<12} {format_size(row['index_bytes']):<12} "
              f"{format_size(row['total_bytes']):<12} {row['index_count']}")
    
    print()
    print("=" * 80)
    print("按模型分类汇总")
    print("=" * 80)
    print()
    
    # 按模型分类汇总
    for category, tables in category_stats.items():
        if not tables:
            continue
            
        print(f"{category}:")
        print("-" * 65)
        
        # 计算总计
        total_data = sum(t['data_bytes'] for t in tables)
        total_index = sum(t['index_bytes'] for t in tables)
        total_size = sum(t['total_bytes'] for t in tables)
        total_indexes = sum(t['index_count'] for t in tables)
        
        # 打印该模型下所有表
        for table in tables:
            sort_order = TABLE_ORDER.get(table['table_name'], 'N/A')
            print(f"  [{sort_order:>2}] {table['table_name']:<23} "
                  f"数据: {format_size(table['data_bytes']):<12} "
                  f"索引: {format_size(table['index_bytes']):<12} "
                  f"索引数: {table['index_count']}")
        
        print(f"  {'-' * 60}")
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
    
    print("=" * 80)
    print("数据库总计")
    print("=" * 80)
    print(f"总数据大小: {format_size(total_data)}")
    print(f"总索引大小: {format_size(total_index)}")
    print(f"总占用空间: {format_size(total_size)}")
    print(f"索引总数: {total_indexes}")
    print("=" * 80)

def main():
    """主函数"""
    print(f"正在连接ArangoDB: {ARANGO_CONF['hosts']}...")
    
    try:
        client = ArangoClient(hosts=ARANGO_CONF['hosts'])
        db = client.db(
            ARANGO_CONF['dbname'],
            username=ARANGO_CONF['username'],
            password=ARANGO_CONF['password']
        )
        print("连接成功！")
        
        raw_stats = get_all_collections_stats(db)
        
        # 检查缺失集合
        found_collections = {row['table_name'] for row in raw_stats}
        expected_collections = set(TABLE_ORDER.keys())
        missing_collections = expected_collections - found_collections
        
        if missing_collections:
            print(f"\n警告: 以下集合在数据库中未找到: {', '.join(missing_collections)}")
        
        stats = sort_by_custom_order(raw_stats)
        category_stats = categorize_tables(stats)
        print_summary(stats, category_stats)
        
    except ArangoError as e:
        print(f"ArangoDB错误: {e}")
    except Exception as e:
        print(f"意外错误: {e}")

if __name__ == '__main__':
    main()