import pandas as pd
import numpy as np
import os
import json
import sys
import csv
from tqdm import tqdm
from collections import defaultdict

# --- 配置 (路径) ---

MAX_AUTHORS_PER_PAPER_CUTOFF = 30

WEIGHT_WORKS_COUNT = 0.6  # 生产力权重
WEIGHT_CITED_BY = 0.4   # 影响力权重
MINIMUM_SCORE = 0.001   # 最小分数，防止 0 概率

# --- 统计函数 ---
def extract_topic_vectors_from_csv(output_vec_dir, collect_output_dir):
    """直接把跑好的 topic 向量 CSV 转成内存可读的字典 json"""
    output_json = os.path.join(collect_output_dir, "topic_vectors.json")
    
    # 兼容两种命名（优先找生成目录下的 topics_vec.csv，如果没有就找原始的 384 文件）
    csv_candidates = [
        os.path.join(output_vec_dir, "topics_vec.csv"),
        os.path.join(output_vec_dir, "topics_vector_384.csv")
    ]
    
    vec_dict = {}
    for input_csv in csv_candidates:
        if os.path.exists(input_csv):
            print(f"    找到主题向量文件: {input_csv}，正在转存为字典...")
            import sys
            import csv
            csv.field_size_limit(sys.maxsize)
            
            with open(input_csv, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None) # 跳过表头
                for row in reader:
                    if len(row) >= 2:
                        tid = str(row[0])
                        vec_str = row[-1] # 向量始终在最后一列
                        try:
                            vec_dict[tid] = json.loads(vec_str) 
                        except json.JSONDecodeError:
                            continue
            break # 只要读到一个有效文件，就跳出循环
            
    if vec_dict:
        with open(output_json, 'w') as f:
            json.dump(vec_dict, f)
        print(f"    成功转存了 {len(vec_dict)} 个主题向量到内存字典！")
    else:
        print("    WARNING: 没有找到任何已有的主题向量 CSV 文件。")
def analyze_sf1_stats(csv_dir):
    """
    读取 SF=1 (openalex_small) CSV 文件，统计所有基准数据。
    """
    # print("--- 正在分析 SF=1 基准数据集 (来自 openalex_small)... ---")
    
    stats = {}
    
    try:
        works_file = os.path.join(csv_dir, "works.csv")
        # print(f" 读取: {works_file} ")
        
        df_works = pd.read_csv(works_file, usecols=['id','publication_year'])

        df_works_id_cleaned = df_works.dropna(subset=['id'])
        df_works_id_cleaned['id'] = pd.to_numeric(df_works_id_cleaned['id'], errors='coerce').dropna()
        if not df_works_id_cleaned.empty:
            stats['max_work_id'] = int(df_works_id_cleaned['id'].max())
            # print(f" 找到最大 Work ID: {stats['max_work_id']}")
        else:
            stats['max_work_id'] = 0

        df_works = df_works.dropna(subset=['publication_year'])
        df_works['publication_year'] = pd.to_numeric(
            df_works['publication_year'], errors='coerce'
        ).dropna().astype(int)
        
        valid_years_df = df_works[
            (df_works['publication_year'] > 1900) & 
            (df_works['publication_year'] <= 2025) 
        ]
        
        stats['total_articles'] = int(valid_years_df.shape[0])
        min_year = int(valid_years_df['publication_year'].min())
        max_year = int(valid_years_df['publication_year'].max())
        stats['time_range'] = list(range(min_year, max_year + 1))
        
        article_dist_raw = valid_years_df['publication_year'].value_counts().to_dict()
        stats['article_distribution'] = {
            year: int(article_dist_raw.get(year, 0)) 
            for year in stats['time_range']
        }

        # --- 分析 Authors ---
        authors_file = os.path.join(csv_dir, "authors.csv")
        # print(f" 读取: {authors_file} ")
        df_authors = pd.read_csv(authors_file, usecols=['id'])
        stats['total_authors'] = int(df_authors.shape[0])
        
        df_authors['id'] = pd.to_numeric(df_authors['id'], errors='coerce').dropna()
        if not df_authors.empty:
            stats['max_author_id'] = int(df_authors['id'].max())
            # print(f" 找到最大 Author ID: {stats['max_author_id']}")
        else:
            stats['max_author_id'] = 0
            
        # --- 分析 Topics ---
        topics_file = os.path.join(csv_dir, "topics.csv")
        # print(f" 读取: {topics_file} ")
        df_topics = pd.read_csv(topics_file, usecols=['id'])
        stats['total_topics'] = int(df_topics.shape[0])
        
        # print("--- SF=1 分析完成 ---")
        return stats

    except FileNotFoundError as e:
        print(f"!!! ERROR：找不到文件 {e.filename}")
        print(" 请确保 'openalex_small' 目录与 'data_gen' 目录在同一父目录下。")
        return None
    except Exception as e:
        print(f"ERROR：统计 SF=1 数据时出错: {e}")
        return None

def analyze_author_activity(csv_dir, output_dir):
    """
    计算每个作者的“网络结构资本分数” (Collaborative Structural Capital)
    并保存到 JSON 文件。
    """
    print("--- 分析 作者拓扑活跃度 (基于合作网络结构)... ---")
    
    # 边表路径：指向生成的 SF1 的 authors_authors_e.csv
    edges_file = os.path.join(csv_dir, "authors_authors_e.csv")
    output_file = os.path.join(output_dir, "author_activity_weights.json")

    if not os.path.exists(edges_file):
        print(f"ERROR：找不到合作边表文件 {edges_file}")
        return False

    # author_neighbors 用于计算 Degree (独立合作者数，即协同广度)
    author_neighbors = defaultdict(set)
    # author_collaborations 用于计算 Strength (基于 cnt 累加的总合作次数，即协同深度)
    author_collaborations = defaultdict(int)
    
    # 增加 CSV 字段大小限制，防止超大 JSON 引发报错
    csv.field_size_limit(sys.maxsize)
    
    try:
        with open(edges_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳过表头
            
            for row in tqdm(reader, desc="解析网络拓扑与 JSON", unit="边"):
                # 确保读取到了包含 JSON 的 properties 字段
                if len(row) >= 3:
                    u, v, props_str = row[0], row[1], row[2]
                    
                    if u != v: # 排除自环
                        # 1. 广度：记录独立的合作者
                        author_neighbors[u].add(v)
                        author_neighbors[v].add(u)
                        
                        # 2. 深度：解析 JSON，提取真实的合作次数 (cnt)
                        try:
                            props = json.loads(props_str)
                            # 提取 cnt，如果没有则默认算作 1
                            collab_count = props.get("cnt", 1) 
                        except json.JSONDecodeError:
                            collab_count = 1 
                            
                        # 累加合作总次数
                        author_collaborations[u] += collab_count
                        author_collaborations[v] += collab_count
                        
    except Exception as e:
        print(f"ERROR：读取边表时出错: {e}")
        return False

    if not author_neighbors:
        print("ERROR：没有统计到任何合作记录！")
        return False

    # 将字典转化为 DataFrame 以便进行快速的数学运算
    data = []
    for author_id, neighbors in author_neighbors.items():
        data.append({
            'id': author_id,
            'degree': len(neighbors),                # 协同广度
            'strength': author_collaborations[author_id] # 协同深度
        })
    df = pd.DataFrame(data)

    print(f" 提取到 {len(df):,} 名具有网络结构的活跃作者。开始计算 CSCI 分数...")

    # ==========================================
    # 数学处理：Log1p 平滑 + Min-Max 归一化
    # ==========================================
    df['log_degree'] = np.log1p(df['degree'])
    df['log_strength'] = np.log1p(df['strength'])

    # 归一化：协同广度
    if df['log_degree'].max() - df['log_degree'].min() > 0:
        df['norm_degree'] = (df['log_degree'] - df['log_degree'].min()) / \
                            (df['log_degree'].max() - df['log_degree'].min())
    else:
        df['norm_degree'] = 0.0 

    # 归一化：协同深度
    if df['log_strength'].max() - df['log_strength'].min() > 0:
        df['norm_strength'] = (df['log_strength'] - df['log_strength'].min()) / \
                              (df['log_strength'].max() - df['log_strength'].min())
    else:
        df['norm_strength'] = 0.0 

    # ==========================================
    # 权重融合 (严格按照要求：合作作者数占 80%)
    # ==========================================
    WEIGHT_BREADTH = 0.8  # 协同广度 (独立合作者数) 占比 80%
    WEIGHT_DEPTH = 0.2    # 协同深度 (合作总次数 cnt) 占比 20%
    MINIMUM_SCORE = 1e-4  # 极小值保底

    df['activity_score'] = (WEIGHT_BREADTH * df['norm_degree']) + \
                           (WEIGHT_DEPTH * df['norm_strength'])
                           
    df['activity_score'] = df['activity_score'].replace(0, MINIMUM_SCORE)
    
    # 构建最终的权重字典并保存
    activity_weights = dict(zip(df['id'].astype(str), df['activity_score']))

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(activity_weights, f) 
        print(f" 作者网络结构资本权重 (Degree 80%, cnt 20%) 已保存到: {output_file}\n")
        return True
        
    except Exception as e:
        print(f"ERROR：保存 JSON 文件时出错: {e}\n")
        return False

def analyze_author_fields(csv_dir, graph_edges_dir, output_dir):
    """
    为每个作者计算其最主要的研究领域 (Field 和 Subfield) 。
    """
    # print("--- 正在分析 作者主要领域 (合并4个CSV)... ---")
    
    authors_file = os.path.join(csv_dir, "authors.csv")
    topics_file = os.path.join(csv_dir, "topics.csv")
    works_authors_e_file = os.path.join(graph_edges_dir, "works_authors_e.csv")
    works_topics_e_file = os.path.join(graph_edges_dir, "works_topics_e.csv")
    output_file = os.path.join(output_dir, "author_primary_fields.json")
    institutions_file = os.path.join(csv_dir, "institutions.csv")

    try:
        # print(f" 正在加载: {institutions_file} (用于名称映射)")
        df_institutions = pd.read_csv(
            institutions_file,
            usecols=['id', 'display_name'],
            dtype={'id': str, 'display_name': str}
        )
        df_institutions = df_institutions.dropna(subset=['id'])
        # 2. 构建机构 ID -> Name 的映射字典
        institution_name_map = dict(zip(df_institutions['id'], df_institutions['display_name']))
        # print(f" 机构名称映射构建完毕 (共 {len(institution_name_map)} 条)。")

        # print(f" 正在加载: {topics_file}")
        df_topics = pd.read_csv(
            topics_file, 
            usecols=['id', 'field_id', 'subfield_id'],
            dtype={'id': str, 'field_id': str, 'subfield_id': str}
        )
        df_topics['id'] = pd.to_numeric(df_topics['id'], errors='coerce')
        df_topics = df_topics.dropna(subset=['id'])
        df_topics['id'] = df_topics['id'].astype(np.int64)

        # print(f" 正在加载: {works_topics_e_file}")
        df_work_topics = pd.read_csv(
            works_topics_e_file, 
            usecols=['startid', 'endid'], # 'startid' = work_id, 'endid' = topic_id
            dtype={'startid': np.int64, 'endid': np.int64}
        )
        df_work_topics.rename(columns={'startid': 'work_id', 'endid': 'topic_id'}, inplace=True)

        # print(f" 正在加载: {works_authors_e_file}")
        df_author_works = pd.read_csv(
            works_authors_e_file, 
            usecols=['startid', 'endid'], # 'startid' = work_id, 'endid' = author_id
            dtype={'startid': np.int64, 'endid': np.int64}
        )
        df_author_works.rename(columns={'startid': 'work_id', 'endid': 'author_id'}, inplace=True)
        
        # print(" 数据加载完成。开始合并 (Merge)...")

        df_merged = pd.merge(df_author_works, df_work_topics, on='work_id')
        df_final_merged = pd.merge(
            df_merged, 
            df_topics, 
            left_on='topic_id', 
            right_on='id'
        )
        
        # print(" 合并完成。开始计算众数 (Mode)... ")
        
        def get_primary_field_series(group_col_name):
            """计算 Field 或 Subfield 的众数"""
            counts = df_final_merged.groupby('author_id')[group_col_name].value_counts()
            idx_of_max_counts = counts.groupby(level=0).idxmax(skipna=True).dropna()
            primary_series = counts.loc[idx_of_max_counts] \
                                   .reset_index() \
                                   .drop_duplicates(subset='author_id') \
                                   .set_index('author_id')[group_col_name]
            return primary_series

        primary_fields_series = get_primary_field_series('field_id')
        primary_subfields_series = get_primary_field_series('subfield_id')

        # print(" 众数计算完成。")
        
        # print(f" 正在加载: {authors_file} ")
        df_all_authors = pd.read_csv(
            authors_file, 
            usecols=['id', 'institution_id', 'display_name'], 
            dtype={'id': np.int64, 'institution_id': str, 'display_name': str} 
        )
        
        df_all_authors['institution_id'] = df_all_authors['institution_id'].astype(object).where(
            pd.notna(df_all_authors['institution_id']), None
        )
        df_all_authors['display_name'] = df_all_authors['display_name'].fillna("Unknown Name")

        author_institution_map = df_all_authors.set_index('id')['institution_id'].to_dict()
        author_name_map = df_all_authors.set_index('id')['display_name'].to_dict()

        primary_fields_map = primary_fields_series.to_dict()
        primary_subfields_map = primary_subfields_series.to_dict()

        final_author_data = {}
        # print(" 构建作者领域映射...")
        

        for author_id in tqdm(df_all_authors['id'], desc="构建作者领域 Map"):
            institution_id = author_institution_map.get(author_id)
            institution_name = institution_name_map.get(institution_id)
            final_author_data[str(author_id)] = {
                "field": primary_fields_map.get(author_id),
                "subfield": primary_subfields_map.get(author_id),
                "institution_id": institution_id,
                "display_name": author_name_map.get(author_id),
                "institution_display_name": institution_name
            }
        
        # print(f" 共处理 {len(final_author_data)} 名作者。")

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_author_data, f) # 不使用 indent 节省空间
            # print(f" 作者主要领域已保存到: {output_file}\n")
            return True
            
        except Exception as e:
            print(f"ERROR：保存 JSON 文件时出错: {e}\n")
            return False

    except FileNotFoundError as e:
        print(f"ERROR：找不到文件 {e.filename}")
        return False
    except Exception as e:
        print(f"ERROR：预计算时出错: {e}")
        return False

def analyze_author_paper_distribution(graph_edges_dir, output_dir):
    """
    统计“每篇论文的作者数量”的分布。
    """
    
    input_file = os.path.join(graph_edges_dir, "works_authors_e.csv")
    output_file = os.path.join(output_dir, "authors_per_paper_dist.json")

    try:
        df_edges = pd.read_csv(
            input_file,
            usecols=['startid'], 
            dtype={'startid': np.int64}
        )
        author_counts_per_work = df_edges.groupby('startid').size()        
        total_papers = len(author_counts_per_work)
        filtered_counts = author_counts_per_work[author_counts_per_work <= MAX_AUTHORS_PER_PAPER_CUTOFF]
        
        filtered_papers = len(filtered_counts)
        outlier_papers = total_papers - filtered_papers
        
        distribution = filtered_counts.value_counts(normalize=True) 
        
        distribution_dict = {str(k): v for k, v in distribution.to_dict().items()}

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(distribution_dict, f, indent=4)
            return True
        except Exception as e:
            print(f"ERROR：保存 JSON 文件时出错: {e}\n")
            return False

    except FileNotFoundError as e:
        print(f"ERROR：找不到文件 {e.filename}")
        return False
    except Exception as e:
        print(f"ERROR：预计算时出错: {e}")
        return False

def analyze_author_collaboration_graph(graph_edges_dir, output_dir):
    """
    精简合作边表，防止内存溢出
    """
    
    input_file = os.path.join(graph_edges_dir, "authors_authors_e.csv")
    output_file = os.path.join(output_dir, "author_coauthor_graph.json")
    
    chunk_size = 5_000_000 
    
    coauthor_graph = defaultdict(list)
    
    try:
        
        reader = pd.read_csv(
            input_file,
            usecols=['startid', 'endid'], # 'startid' = author1, 'endid' = author2 
            dtype={'startid': np.int64, 'endid': np.int64},
            chunksize=chunk_size
        )
        
        for chunk in tqdm(reader, desc="处理合作图"):
            for row in chunk.itertuples(index=False):
                author1_id_str = str(row.startid)
                author2_id_str = str(row.endid)               
                coauthor_graph[author1_id_str].append(author2_id_str)
                coauthor_graph[author2_id_str].append(author1_id_str)

        # 去重
        for author_id in tqdm(coauthor_graph, desc="去重合作边表"):
             coauthor_graph[author_id] = list(set(coauthor_graph[author_id]))

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(coauthor_graph, f) 
            return True
        except Exception as e:
            print(f" ERROR：保存 JSON 文件时出错: {e}\n")
            return False

    except FileNotFoundError as e:
        print(f" ERROR：找不到文件 {e.filename}")
        return False
    except Exception as e:
        print(f" ERROR：预计算时出错: {e}")
        return False

def analyze_topic_hierarchy_and_hotness(csv_dir, all_topics_file_path, output_dir):
    """
    预处理topic
    """
    
    small_topics_file = os.path.join(csv_dir, "topics.csv")
    all_topics_file = all_topics_file_path
    
    output_hotness_file = os.path.join(output_dir, "topic_hotness.json")
    output_hierarchy_existing_file = os.path.join(output_dir, "topic_hierarchy_existing.json") 
    output_hierarchy_new_file = os.path.join(output_dir, "topic_hierarchy_new.json") 
    output_field_hierarchy_file = os.path.join(output_dir, "field_hierarchy_existing.json")
    
    try:
        df_small_topics = pd.read_csv(
            small_topics_file,
            usecols=['id'],
            dtype={'id': str}
        )
        df_small_topics['id'] = pd.to_numeric(df_small_topics['id'], errors='coerce')
        df_small_topics = df_small_topics.dropna()

        small_topic_ids_set = set(df_small_topics['id'].astype(np.int64))

        df_all_topics = pd.read_csv(
            all_topics_file,
            usecols=['id', 'subfield_id', 'field_id', 'works_count', 'cited_by_count'],
            dtype={'id': str, 'subfield_id': str, 'field_id': str, 'works_count': float, 'cited_by_count': float}
        )

        df_all_topics['id'] = pd.to_numeric(df_all_topics['id'], errors='coerce')
        df_all_topics = df_all_topics.dropna(subset=['id'])
        df_all_topics['id'] = df_all_topics['id'].astype(np.int64)
        df_all_topics['works_count'] = df_all_topics['works_count'].fillna(0)
        df_all_topics['cited_by_count'] = df_all_topics['cited_by_count'].fillna(0)

        df_all_topics['log_works'] = np.log1p(df_all_topics['works_count'])
        df_all_topics['log_cites'] = np.log1p(df_all_topics['cited_by_count'])

        min_log_works = df_all_topics.groupby('subfield_id')['log_works'].transform('min')
        max_log_works = df_all_topics.groupby('subfield_id')['log_works'].transform('max')
        range_log_works = max_log_works - min_log_works
        
        min_log_cites = df_all_topics.groupby('subfield_id')['log_cites'].transform('min')
        max_log_cites = df_all_topics.groupby('subfield_id')['log_cites'].transform('max')
        range_log_cites = max_log_cites - min_log_cites

        df_all_topics['norm_works'] = (
            (df_all_topics['log_works'] - min_log_works) / range_log_works
        ).replace([np.inf, -np.inf], 0).fillna(0)
        
        df_all_topics['norm_cites'] = (
            (df_all_topics['log_cites'] - min_log_cites) / range_log_cites
        ).replace([np.inf, -np.inf], 0).fillna(0)
        
        df_all_topics['hot_score'] = (WEIGHT_WORKS_COUNT * df_all_topics['norm_works']) + \
                                     (WEIGHT_CITED_BY * df_all_topics['norm_cites'])
        
        df_all_topics['hot_score'] = df_all_topics['hot_score'].replace(0, MINIMUM_SCORE)
        
        topic_hotness_dict = dict(zip(df_all_topics['id'].astype(str), df_all_topics['hot_score']))


        hierarchy_existing = defaultdict(list)
        hierarchy_new = defaultdict(list)
        field_hierarchy_existing = defaultdict(list)
        df_filtered = df_all_topics
        
        for row in tqdm(df_filtered.itertuples(index=False), total=len(df_filtered), desc=" "):
            topic_id = row.id 
            topic_id_str = str(topic_id)
            subfield_id_str = str(row.subfield_id)
            field_id_str = str(row.field_id)
            if pd.notna(row.subfield_id):
                if topic_id in small_topic_ids_set:
                    hierarchy_existing[subfield_id_str].append(topic_id_str)
                else:
                    hierarchy_new[subfield_id_str].append(topic_id_str)

            if pd.notna(row.field_id) and (topic_id in small_topic_ids_set):
                clean_fid = field_id_str.split('/')[-1]
                field_hierarchy_existing[clean_fid].append(topic_id_str)
        
        try:
            with open(output_hotness_file, 'w', encoding='utf-8') as f:
                json.dump(topic_hotness_dict, f)
            # print(f" 主题热度 (All) 已保存到: {output_hotness_file}")
            
            with open(output_hierarchy_existing_file, 'w', encoding='utf-8') as f:
                json.dump(hierarchy_existing, f)
            # print(f" 已存在主题已保存到: {output_hierarchy_existing_file}")
            
            with open(output_hierarchy_new_file, 'w', encoding='utf-8') as f:
                json.dump(hierarchy_new, f)
            # print(f" 新主题库已保存到: {output_hierarchy_new_file}")
            with open(output_field_hierarchy_file, 'w', encoding='utf-8') as f:
                json.dump(field_hierarchy_existing, f)
            # print(f"\n--- 主题信息统计成功！ ---\n")
            return True
            
        except Exception as e:
            print(f"ERROR：保存 JSON 文件时出错: {e}\n")
            return False

    except FileNotFoundError as e:
        print(f"ERROR：找不到文件 {e.filename}")
        return False
    except Exception as e:
        print(f"ERROR：预计算时出错: {e}")
        return False


def analyze_citation_count_distribution(graph_edges_dir, output_dir):
    """
    统计每篇论文引文数量分布。
    """
    
    input_file = os.path.join(graph_edges_dir, "works_referenced_works_e.csv")
    output_file = os.path.join(output_dir, "citation_count_dist.json")

    try:
        df_edges = pd.read_csv(
            input_file,
            usecols=['startid'], # 'startid' 是引用者 (citing paper)
            dtype={'startid': np.int64}
        )
        
        citation_counts_per_work = df_edges.groupby('startid').size()
        
        MIN_CITATIONS = 1
        MAX_CITATIONS = 40
        filtered_counts = citation_counts_per_work[
            (citation_counts_per_work >= MIN_CITATIONS) &
            (citation_counts_per_work <= MAX_CITATIONS)
        ]
        # print(f" 已将引文数截断在 [{MIN_CITATIONS}, {MAX_CITATIONS}] 范围内。")

        distribution = filtered_counts.value_counts(normalize=True)
        distribution_dict = {str(k): v for k, v in distribution.to_dict().items()}

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(distribution_dict, f, indent=4)
            return True
        except Exception as e:
            print(f"ERROR：保存 JSON 文件时出错: {e}\n")
            return False

    except FileNotFoundError as e:
        print(f"ERROR：找不到文件 {e.filename}")
        return False
    except Exception as e:
        print(f"ERROR：预计算时出错: {e}")
        return False

def analyze_citation_pools(csv_dir, graph_edges_dir, output_dir):
    """
    构建引文采样池。
    """
    
    works_file = os.path.join(csv_dir, "works.csv")
    works_topics_file = os.path.join(graph_edges_dir, "works_topics_e.csv")
    topics_file = os.path.join(csv_dir, "topics.csv") 
    
    output_topic_pool_file = os.path.join(output_dir, "topic_to_papers_pool.json")
    output_subfield_pool_file = os.path.join(output_dir, "subfield_to_papers_pool.json")

    try:
        # 加载 works (id 和 cited_by_count)
        df_works = pd.read_csv(works_file, usecols=['id', 'cited_by_count'], dtype={'id': np.int64, 'cited_by_count': float}).dropna().astype({'cited_by_count': np.int64})
        # 加载 topics (id, subfield_id)
        df_topics = pd.read_csv(topics_file, usecols=['id', 'subfield_id'], dtype={'id': str, 'subfield_id': str})
        df_topics['id'] = pd.to_numeric(df_topics['id'], errors='coerce').dropna().astype({'id': np.int64})
        # 加载 works_topics
        df_work_topics = pd.read_csv(works_topics_file, usecols=['startid', 'endid'], dtype={'startid': np.int64, 'endid': np.int64}).rename(columns={'startid': 'id', 'endid': 'topic_id'})
        
        # 合并
        df_merged_1 = pd.merge(df_works, df_work_topics, on='id')
        df_final = pd.merge(df_merged_1, df_topics, left_on='topic_id', right_on='id')
        
        # 构建 Topic -> Papers 池
        topic_to_papers_pool = defaultdict(list)
        for row in tqdm(df_final.itertuples(index=False), total=len(df_final), desc="构建 Topic 池"):
            topic_to_papers_pool[str(row.topic_id)].append((row.id_x, row.cited_by_count))

        # 构建 Subfield -> Papers 池 
        subfield_to_papers_pool = defaultdict(list)
        df_subfield = df_final.dropna(subset=['subfield_id'])
        for row in tqdm(df_subfield.itertuples(index=False), total=len(df_subfield), desc="构建 Subfield 池"):
            subfield_to_papers_pool[str(row.subfield_id)].append((row.id_x, row.cited_by_count))
            
        # 保存文件
        try:
            with open(output_topic_pool_file, 'w', encoding='utf-8') as f:
                json.dump(topic_to_papers_pool, f)
            # print(f" Topic 引文池已保存到: {output_topic_pool_file}")
            
            with open(output_subfield_pool_file, 'w', encoding='utf-8') as f:
                json.dump(subfield_to_papers_pool, f)
            # print(f" Subfield 引文池已保存到: {output_subfield_pool_file}")
                
            return True
        except Exception as e:
            print(f"ERROR：保存 JSON 文件时出错: {e}\n")
            return False

    except FileNotFoundError as e:
        print(f"ERROR：找不到文件 {e.filename}")
        return False
    except Exception as e:
        print(f"ERROR：预计算时出错: {e}")
        return False

def analyze_work_type_distribution(csv_dir, output_dir):
    """
    统计 'works.csv' 中 'type' 列的概率分布。
    """
    input_file = os.path.join(csv_dir, "works.csv")
    output_file = os.path.join(output_dir, "work_type_dist.json")
    
    try:
        df = pd.read_csv(input_file, usecols=['type'])
        distribution = df['type'].value_counts(normalize=True)
        distribution_dict = {str(k): v for k, v in distribution.to_dict().items()}
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(distribution_dict, f, indent=4)
            
        return True

    except Exception as e:
        print(f"ERROR：预计算时出错: {e}")
        return False

def analyze_work_language_distribution(csv_dir, output_dir):
    """
    统计 'works.csv' 中 'language' 列的概率分布。
    只保留 Top 5 语言 + 'other'
    """

    input_file = os.path.join(csv_dir, "works.csv")
    output_file = os.path.join(output_dir, "work_language_dist.json")
    
    try:
        df = pd.read_csv(input_file, usecols=['language'])
        
        total_count = len(df)
        distribution = df['language'].value_counts()
        top_5_dist = distribution.head(5)
        top_5_prob = top_5_dist / total_count
        other_prob = 1.0 - top_5_prob.sum()
        distribution_dict = {str(k): v for k, v in top_5_prob.to_dict().items()}
        if other_prob > 0.001:
             distribution_dict["other"] = other_prob
             
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(distribution_dict, f, indent=4)

        return True

    except Exception as e:
        print(f"ERROR：预计算时出错: {e}")
        return False
    
def analyze_topic_text_for_vectors(all_topics_file_path, output_dir):
    """
    构建 {id: keywords} 的映射表，用于实时生成 Topic 向量。
    如果 keywords 为空，回退使用 display_name。
    """
    
    output_file = os.path.join(output_dir, "topic_text_map.json")
    topic_text_map = {}
    
    try:
        # 读取 topics_all.csv
        # 假设包含 columns: id, keywords, display_name
        df = pd.read_csv(
            all_topics_file_path, 
            usecols=['id', 'keywords', 'display_name'],
            dtype={'id': str, 'keywords': str, 'display_name': str}
        )
        
        for row in tqdm(df.itertuples(index=False), total=len(df), desc="构建文本Map"):
            # 优先使用 keywords，如果没有则使用 display_name
            text = row.keywords if (pd.notna(row.keywords) and row.keywords.strip()) else row.display_name
            if pd.isna(text):
                text = "Unknown Topic"
            topic_text_map[row.id] = text.lower() 
            
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(topic_text_map, f)
        return True
        
    except Exception as e:
        print(f" ERROR: 构建 Topic 文本表失败: {e}")
        return False

def analyze_topic_mapping(all_topics_file_path, output_dir):
    """
    构建 {TopicID : SubfieldID} 的映射表并保存为 JSON。
    用于在生成摘要时，如果找不到 Topic 模型，可以回退到 Subfield 模型。
    """  
    # output_file = os.path.join(output_dir, "topic_subfield_map.json")
    output_sub_file = os.path.join(output_dir, "topic_subfield_map.json")
    output_field_file = os.path.join(output_dir, "topic_field_map.json")
    # mapping = {}
    sub_mapping = {}
    field_mapping = {}
    
    try:
        # 读取 topics_all.csv
        df = pd.read_csv(
            all_topics_file_path, 
            usecols=['id', 'subfield_id', 'field_id'],
            dtype={'id': str, 'subfield_id': str, 'field_id': str}
        )
        
        for row in tqdm(df.itertuples(index=False), total=len(df), desc="构建映射"):
            if pd.notna(row.id):
                if pd.notna(row.subfield_id):
                # 确保 Subfield ID 也是纯数字字符串 (OpenAlex URL 需切割)
                    sid = str(row.subfield_id).split('/')[-1]
                    sub_mapping[row.id] = sid
                if pd.notna(row.field_id):
                    fid = str(row.field_id).split('/')[-1]
                    field_mapping[row.id] = fid
            
        with open(output_sub_file, 'w', encoding='utf-8') as f:
            json.dump(sub_mapping, f)
        with open(output_field_file, 'w', encoding='utf-8') as f:
            json.dump(field_mapping, f)
        return True
        
    except Exception as e:
        print(f" ERROR: 构建 Topic->Subfield 映射表失败: {e}")
        return False
# ...  ...

# --- 主执行 ---
if __name__ == "__main__":
    print("====== 开始执行【阶段一】一次性预计算 ======")
    if len(sys.argv) != 5:
        print("错误: precompute_statistics.py 期望 4 个路径参数:")
        print("  1. <source_csv_dir> (例如: .../openalex_small/csv-files)")
        print("  2. <source_edges_dir> (例如: .../openalex_small/graph_edges)")
        print("  3. <source_all_topics_path> (例如: .../openalex_small/csv-files/topics_all.csv)")
        print("  4. <output_json_dir> (例如: .../collect_output)")
        sys.exit(1)

    SOURCE_CSV_DIR = sys.argv[1]
    SOURCE_EDGES_DIR = sys.argv[2]
    SOURCE_ALL_TOPICS = sys.argv[3]
    OUTPUT_DIR = sys.argv[4]
    print(f"====== 开始执行预计算 ======")
    # print(f"  输入 CSV 目录: {SOURCE_CSV_DIR}")
    # print(f"  输入 Edges 目录: {SOURCE_EDGES_DIR}")
    # print(f"  输入 Topics (All) 文件: {SOURCE_ALL_TOPICS}")
    # print(f"  输出 JSON 目录: {OUTPUT_DIR}")

    if not os.path.exists(OUTPUT_DIR):
        print(f" 正在创建输出目录: {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR)
    
    stats_data = analyze_sf1_stats(SOURCE_CSV_DIR)
    
    if stats_data:
        output_file = os.path.join(OUTPUT_DIR, "sf1_stats.json")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=4)
            # print(f" SF=1 基准统计数据已保存到: {output_file}\n")
            
        except Exception as e:
            print(f"ERROR：保存 JSON 文件时出错: {e}\n")
    else:
        print("--- 失败！跳过保存。---\n")

    # --- 作者活跃度  ---
    analyze_author_activity(SOURCE_EDGES_DIR, OUTPUT_DIR)
    analyze_author_fields(SOURCE_CSV_DIR, SOURCE_EDGES_DIR, OUTPUT_DIR)
    analyze_author_paper_distribution(SOURCE_EDGES_DIR, OUTPUT_DIR)
    analyze_author_collaboration_graph(SOURCE_EDGES_DIR, OUTPUT_DIR)
    analyze_topic_hierarchy_and_hotness(SOURCE_CSV_DIR, SOURCE_ALL_TOPICS, OUTPUT_DIR)
    analyze_citation_count_distribution(SOURCE_EDGES_DIR, OUTPUT_DIR)
    analyze_citation_pools(SOURCE_CSV_DIR, SOURCE_EDGES_DIR, OUTPUT_DIR)
    analyze_work_type_distribution(SOURCE_CSV_DIR, OUTPUT_DIR)
    analyze_work_language_distribution(SOURCE_CSV_DIR, OUTPUT_DIR)
    analyze_topic_text_for_vectors(SOURCE_ALL_TOPICS, OUTPUT_DIR)
    analyze_topic_mapping(SOURCE_ALL_TOPICS, OUTPUT_DIR)
    OUTPUT_BASE_DIR = os.path.dirname(SOURCE_CSV_DIR)
    VECTOR_DIR = os.path.join(OUTPUT_BASE_DIR, "vector")
    
    extract_topic_vectors_from_csv(VECTOR_DIR, OUTPUT_DIR)
    print("====== 所有预处理已完成。 ======")