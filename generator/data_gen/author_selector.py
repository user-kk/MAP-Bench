import pandas as pd
import numpy as np
import os
import json
import random
import sys
from tqdm import tqdm
import author_generate

class AuthorSelector:

    def __init__(self, activity_weights, primary_fields, author_count_dist,
                 coauthor_graph):

        # print(" 正在加载统计信息...")
        self.activity_weights = activity_weights
        self.primary_fields = primary_fields
        self.author_count_dist = author_count_dist
        self.coauthor_graph = coauthor_graph

        # print(" 正在构建活跃度采样池...")
        self.author_ids_list = list(self.activity_weights.keys())
        self.author_weights_list = list(self.activity_weights.values())
        total_weight = sum(self.author_weights_list)
        if total_weight > 0:
            self.author_weights_probs = [w / total_weight for w in self.author_weights_list]
        else:
            self.author_weights_probs = None

        # 领域反向索引
        # print("    ... 正在构建领域反向索引...")
        self.field_to_authors_index = self._build_field_index()

        # 论文作者数分布
        self.author_count_dist_processed = {
            int(k): v for k, v in self.author_count_dist.items()
        }
        self.author_count_keys = list(self.author_count_dist_processed.keys())
        self.author_count_probs = list(self.author_count_dist_processed.values())

    def _build_field_index(self):
        """构建 'field_id -> [author_id]' 的反向索引"""
        index = {}
        for author_id_str, fields in self.primary_fields.items():
            field = fields.get("field")
            if field:
                if field not in index:
                    index[field] = []
                index[field].append(author_id_str)
        return index

    def _determine_author_count(self):
        """ 确定作者总数 n  """
        if not self.author_count_keys:
            return random.randint(1, 5)
        return np.random.choice(self.author_count_keys, p=self.author_count_probs)

    def _determine_core_count(self, n):
        """ 确定核心作者数量 """
        if n == 1:
            return 1
        if n <= 5:
            return np.random.choice([1, 2], p=[0.7, 0.3])
        return np.random.choice([2, 3], p=[0.6, 0.4])

    def _select_core_team(self, n_cores=1):
        """ 选择 n_cores个“领域相关”的核心作者  """

        if not self.author_ids_list: # 容错
            print(" ERROR：活跃度池为空！")
            return set(), None, None

        core_a_id = np.random.choice(self.author_ids_list, p=self.author_weights_probs)
        core_team_ids = {core_a_id}

        author_info = self.primary_fields.get(core_a_id, {})
        seed_field = author_info.get("field")
        seed_subfield = author_info.get("subfield")
        seed_institution_id = author_info.get("institution_id")

        if n_cores > 1:
            if seed_field and seed_field in self.field_to_authors_index:
                domain_pool_ids = self.field_to_authors_index[seed_field]
                domain_pool_ids = [id for id in domain_pool_ids if id != core_a_id]

                if domain_pool_ids:
                    domain_pool_weights = [self.activity_weights.get(id, 0) for id in domain_pool_ids]
                    total_domain_weight = sum(domain_pool_weights)

                    if total_domain_weight > 0:
                        domain_pool_probs = [w / total_domain_weight for w in domain_pool_weights]
                        n_remaining_cores = min(n_cores - 1, len(domain_pool_ids))

                        other_cores = np.random.choice(
                            domain_pool_ids,
                            size=n_remaining_cores,
                            p=domain_pool_probs,
                            replace=False
                        )
                        core_team_ids.update(other_cores)

            while len(core_team_ids) < n_cores:
                extra_core_id = np.random.choice(self.author_ids_list, p=self.author_weights_probs)
                core_team_ids.add(extra_core_id)

        return core_team_ids, seed_field, seed_subfield, seed_institution_id,core_a_id

    def _expand_with_collaborators(self, final_team_set, core_team_ids, n_to_fill):
        """模拟扩展团队"""
        if n_to_fill <= 0:
            return 0

        # 统一将 final_team_set 里的元素转为字符串用于比对，防止 int/str 混淆
        current_team_str = {str(x) for x in final_team_set}

        # --- 阶段 A：收集 1-hop 熟人 ---
        hop1_candidates = set()
        for core_id in core_team_ids:
            buddies = self.coauthor_graph.get(str(core_id), [])
            hop1_candidates.update(buddies)

        valid_hop1 = list(hop1_candidates - current_team_str)

        attempts = 0
        while n_to_fill > 0 and valid_hop1 and attempts < len(valid_hop1) * 2:
            new_collab = str(random.choice(valid_hop1))
            if new_collab not in current_team_str:
                final_team_set.add(new_collab)
                current_team_str.add(new_collab)
                n_to_fill -= 1
            attempts += 1

        if n_to_fill <= 0:
            return 0

        # --- 阶段 B：收集 2-hop (熟人的熟人) ---
        hop2_candidates = set()
        for buddy_id in hop1_candidates:
            buddies_of_buddy = self.coauthor_graph.get(str(buddy_id), [])
            hop2_candidates.update(buddies_of_buddy)

        valid_hop2 = list(hop2_candidates - current_team_str - hop1_candidates)

        attempts = 0
        while n_to_fill > 0 and valid_hop2 and attempts < len(valid_hop2) * 2:
            new_collab = str(random.choice(valid_hop2))
            if new_collab not in current_team_str:
                final_team_set.add(new_collab)
                current_team_str.add(new_collab)
                n_to_fill -= 1
            attempts += 1

        return n_to_fill # 返回还没凑齐的人数
        # attempts = 0
        # max_attempts = n_to_fill * 3
        # while n_to_fill > 0 and attempts < max_attempts:
        #     seed_author_id = random.choice(list(core_team_ids))
        #     buddies = self.coauthor_graph.get(seed_author_id, [])
        #     valid_buddies = [b_id for b_id in buddies if str(b_id) not in final_team_set]

        #     if valid_buddies:
        #         new_collaborator = str(random.choice(valid_buddies))
        #         final_team_set.add(new_collaborator)
        #         n_to_fill -= 1
        #     attempts += 1
        # return n_to_fill

    def _smart_fallback_fill(self, final_team_set, n_to_fill, seed_field, seed_subfield, seed_institution_id, current_year, new_authors_dict):
        """
        极度克制的智能保底策略 (8-2开)
        """
        if n_to_fill <= 0:
            return

        current_team_str = {str(x) for x in final_team_set}

        # 拿到同领域的候选池
        domain_pool_ids = self.field_to_authors_index.get(seed_field, [])
        valid_domain_pool = [aid for aid in domain_pool_ids if str(aid) not in current_team_str]

        # 预先计算“反向活跃度权重”（专挑没朋友的底层作者）
        inv_probs = []
        if valid_domain_pool:
            domain_weights = [self.activity_weights.get(str(aid), 1e-4) for aid in valid_domain_pool]
            # 倒数处理：原本分数越低，现在权重越高
            inv_weights = [1.0 / (w + 1e-4) for w in domain_weights]
            total_inv = sum(inv_weights)
            inv_probs = [w / total_inv for w in inv_weights]

        for _ in range(n_to_fill):
            # 80% 的概率：或者同领域确实没人了，强制生成新作者！
            if random.random() < 0.80 or not valid_domain_pool:
                new_author_data = author_generate.get_new_author(seed_field, seed_subfield, seed_institution_id, current_year)
                new_id_str = str(new_author_data["id"])

                final_team_set.add(new_id_str)
                current_team_str.add(new_id_str)
                # 记录在本次生成的新作者字典中
                new_authors_dict[new_id_str] = new_author_data
            else:
                # 20% 的概率：捞一个边缘老作者（按反向活跃度抽卡）
                filler = str(np.random.choice(valid_domain_pool, p=inv_probs))

                final_team_set.add(filler)
                current_team_str.add(filler)
    def _format_team_output(self, team_id_set, new_authors_dict, core_a_id=0):
        """ 输出 """
        output_list = []

        for author_id_str in team_id_set:
            if author_id_str in new_authors_dict:
                # 如果这个 ID 是本次刚生成的全新作者
                new_author_data = new_authors_dict[author_id_str]
                fields = self.primary_fields.get(str(core_a_id), {})
                new_author_data["institution_display_name"] = fields.get("institution_display_name")
                output_list.append(new_author_data)
            else:
                # 是已有的老作者
                fields = self.primary_fields.get(author_id_str, {})
                output_list.append({
                    "id": int(author_id_str) if author_id_str is not None else None,
                    "display_name": fields.get("display_name", "Unknown Existing Author"),
                    "primary_field": fields.get("field"),
                    "primary_subfield": fields.get("subfield"),
                    "institution_id": fields.get("institution_id"),
                    "institution_display_name": fields.get("institution_display_name"),
                    "__full_data__": None
                })
        return output_list

    # --- 核心函数 ---
    # def get_author_team(self, p_new_author, current_year):
    #     """
    #     生成作者团队。
    #     Args:
    #         p_new_author (float): 由增量计算器传入的“新作者概率”  。
    #     Returns:
    #         list: 一个作者信息字典的列表  。
    #     """

    #     # 确定作者总数 n
    #     n_total_authors = self._determine_author_count()

    #     final_team_set = set()
    #     new_author_data = None

    #     # 处理“新作者”
    #     if random.random() < p_new_author:
    #         needs_new_author = True
    #         n_existing_to_fill = n_total_authors - 1
    #     else:
    #         needs_new_author = False
    #         n_existing_to_fill = n_total_authors

    #     if n_existing_to_fill <= 0:
    #         if needs_new_author:

    #             # 核心作者
    #             core_team_ids, seed_field, seed_subfield, seed_institution_id,core_a_id = self._select_core_team(n_cores=1)
    #             final_team_set = set()

    #             # 创建新作者
    #             new_author_data = author_generate.get_new_author(seed_field, seed_subfield,seed_institution_id, current_year)
    #             final_team_set.add(new_author_data["id"])

    #             return self._format_team_output(final_team_set, new_author_data), core_team_ids, new_author_data
    #         else:
    #             return [], set(), None # 鲁棒

    #     # 确定并选择核心作者”
    #     n_cores = 1
    #     # n_cores = self._determine_core_count(n_existing_to_fill)
    #     core_team_ids, seed_field, seed_subfield, seed_institution_id,core_a_id = self._select_core_team(n_cores)

    #     final_team_set.update(core_team_ids)

    #     # 创建新作者
    #     if needs_new_author:
    #         new_author_data = author_generate.get_new_author(seed_field, seed_subfield,seed_institution_id, current_year)
    #         final_team_set.add(new_author_data["id"])

    #     # 扩展合作作者
    #     n_to_fill = n_total_authors - len(final_team_set)
    #     if n_to_fill > 0:
    #         n_to_fill = self._expand_with_collaborators(final_team_set, core_team_ids, n_to_fill)

    #     if n_to_fill > 0:
    #         self._fill_with_local_active(final_team_set, n_to_fill,seed_field)

    #     return self._format_team_output(final_team_set, new_author_data,core_a_id), core_team_ids, new_author_data
    def get_author_team(self, p_new_author, current_year):
        """
        生成作者团队主逻辑。
        """
        # 1. 确定作者总数 N
        n_total_authors = self._determine_author_count()

        final_team_set = set()
        new_authors_dict = {} # 字典：存放本篇文章产生的所有新作者

        # 2. 强制单核：抽取核心作者
        core_team_ids, seed_field, seed_subfield, seed_institution_id, core_a_id = self._select_core_team(n_cores=1)
        final_team_set.update({str(x) for x in core_team_ids})

        # 3. 响应外部增量要求：是否保底需要一个新作者
        if random.random() < p_new_author:
            new_author_data = author_generate.get_new_author(seed_field, seed_subfield, seed_institution_id, current_year)
            new_id_str = str(new_author_data["id"])
            final_team_set.add(new_id_str)
            new_authors_dict[new_id_str] = new_author_data

        # 4. 挖熟人：在 1-hop 和 2-hop 里尽力招募
        n_to_fill = n_total_authors - len(final_team_set)
        if n_to_fill > 0:
            n_to_fill = self._expand_with_collaborators(final_team_set, core_team_ids, n_to_fill)

        # 5. 触发 8-2 策略
        if n_to_fill > 0:
            self._smart_fallback_fill(final_team_set, n_to_fill, seed_field, seed_subfield, seed_institution_id, current_year, new_authors_dict)

        # 🚨 注意：第三个返回值现在是一个 LIST，包含了所有新生成的作者
        return self._format_team_output(final_team_set, new_authors_dict, core_a_id), core_team_ids, list(new_authors_dict.values())
