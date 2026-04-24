import random
import numpy as np
import os
import csv
from collections import Counter

class CitationSelector:
    
    M_POPULAR_COUNT = 3
    
    def _build_topic_to_subfield_map(self, path_to_topics_all):
        """加载 topics_all.csv，构建用于回退的映射"""
        # print(" 正在构建 Topic->Subfield 回退映射...")
        mapping = {}
        try:
            with open(path_to_topics_all, 'r', encoding='utf-8', buffering=8*1024*1024) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mapping[row['id']] = row.get('subfield_id')
        except Exception as e:
            print(f"WARNING: 构建回退映射失败: {e}")
        return mapping

    def __init__(self, citation_count_dist, topic_pool, subfield_pool, path_to_topics_all):

        self.topic_pool = topic_pool
        self.subfield_pool = subfield_pool
        
        # 加载引文数量的分布
        self.n_count_keys = [int(k) for k in citation_count_dist.keys()]
        self.n_count_probs = list(citation_count_dist.values())
        # print(" 引文数量 (n) 分布已加载。")
        
        # 加载topic->subfield的映射
        self.topic_to_subfield_map = self._build_topic_to_subfield_map(path_to_topics_all)

    def _sample_citation_count(self):
        """确定引文总数 n """
        if not self.n_count_keys:
            return random.randint(1, 50) 
        return np.random.choice(self.n_count_keys, p=self.n_count_probs)

    def _get_pools(self, topic_id):

        raw_pool = self.topic_pool.get(str(topic_id))
        
        if not raw_pool:
            subfield_id = self.topic_to_subfield_map.get(str(topic_id))
            if subfield_id:
                # print(f" WARNING：Topic {topic_id} 在引文池中为空。正在回退到 Subfield {subfield_id}...")
                raw_pool = self.subfield_pool.get(str(subfield_id))
            if not raw_pool:
                 print(f"        -> Subfield {subfield_id} 池也为空。无法采样。")
                 return [], [] 

        # `m` 池：按 `cited_by_count` 降序排序
        pool_popular_sorted = sorted(raw_pool, key=lambda x: x[1], reverse=True)
        pool_m = [p[0] for p in pool_popular_sorted] # 只取 ID
        
        # `k` 池：同一个池，随机抽
        pool_k = [p[0] for p in raw_pool] # 只取 ID
        random.shuffle(pool_k)
        
        return pool_m, pool_k

    def get_citations(self, selected_topic_metadata):
        """
        主函数
        """
        
        # 获取 `n`, `m`, `k`
        n_total = self._sample_citation_count()
        if n_total == 0:
            return []
            
        m_popular = self.M_POPULAR_COUNT 
        k_random = n_total - m_popular
        if k_random < 0:
            k_random = 0
            
        # 获取 topic_id 
        topic_id = selected_topic_metadata.get("id")
        if not topic_id:
            print(" ERROR：未收到 Topic ID。")
            return []

        # 获取 `k` 池和 `m` 池
        pool_m, pool_k = self._get_pools(topic_id)
        if not pool_m:
            return [] 

        # 采样 `m` 
        n_to_sample_m = min(m_popular, n_total, len(pool_m))
        citations_set = set(pool_m[:n_to_sample_m]) 

        # 采样 `k` 
        pool_k_filtered = [p_id for p_id in pool_k if p_id not in citations_set] # 互斥
        n_remaining_slots = n_total - len(citations_set)
        n_to_sample_k = min(k_random, n_remaining_slots, len(pool_k_filtered))
        
        if n_to_sample_k > 0:
            citations_set.update(pool_k_filtered[:n_to_sample_k]) # (取打乱后的前 k 个)

        # 补齐
        n_to_fill = n_total - len(citations_set)
        if n_to_fill > 0:
            pool_k_fill = [p_id for p_id in pool_k if p_id not in citations_set]
            n_to_sample_fill = min(n_to_fill, len(pool_k_fill))
            if n_to_sample_fill > 0:
                citations_set.update(pool_k_fill[:n_to_sample_fill])       
        return list(citations_set)