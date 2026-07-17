import random
import numpy as np
from collections import Counter
import csv
import os
def _build_topic_name_cache(path_to_topics_all):
    """
    构建 {id: display_name} 映射
    """
    name_cache = {}
    try:
        with open(path_to_topics_all, 'r', encoding='utf-8', buffering=8*1024*1024) as f:
            reader = csv.DictReader(f)
            for row in reader:
                name_cache[row['id']] = row.get('display_name')
    except FileNotFoundError:
        print(f" ERROR: 无法找到 {path_to_topics_all} 来构建名称缓存！")
    except Exception as e:
        print(f" ERROR: 构建名称缓存失败: {e}")

    # print(f" ... 构建完毕，加载了 {len(name_cache)} 个条目。")
    return name_cache
class TopicSelector:

    def __init__(self, topic_hotness, topic_hierarchy_existing, topic_hierarchy_new,field_hierarchy_existing, topic_field_map,path_to_topics_all):

        self.topic_hotness = topic_hotness
        self.h_exist = topic_hierarchy_existing
        self.h_new = topic_hierarchy_new
        self.h_field_exist = field_hierarchy_existing
        self.map_field = topic_field_map
        self.path_to_topics_all = path_to_topics_all
        # self.topics_written_this_run = set()
        self.topic_name_cache = _build_topic_name_cache(path_to_topics_all)


        # print(" ... 正在构建全局热度采样池...")

        self.global_topic_ids = list(self.topic_hotness.keys())

        if not self.global_topic_ids:
            print(" ERROR：热度表为空！")
            self.global_topic_probs = []
        else:
            self.global_topic_probs = [self.topic_hotness[tid] for tid in self.global_topic_ids]
            total_global_prob = sum(self.global_topic_probs)

            if total_global_prob > 0:
                self.global_topic_probs = [p / total_global_prob for p in self.global_topic_probs]
            else:
                self.global_topic_ids = []

    def _get_subfield_mode(self, author_team):
        """
        计算作者团队的 subfield 众数 。
        """
        subfield_list = []
        for author in author_team:
            subfield = author.get("primary_subfield")
            if subfield:
                subfield_list.append(subfield)

        if not subfield_list:
            return None

        mode_subfield = Counter(subfield_list).most_common(1)[0][0]
        return str(mode_subfield)

    def _weighted_sample_from_pool(self, topic_id_pool):
        """
        从给定的 Topic 池中，按热度加权采样 1 个。
        """
        if not topic_id_pool:
            return None, None

        weights = []
        valid_topics = []
        for topic_id in topic_id_pool:
            # score = self.topic_hotness.get(str(topic_id))
            score = self.topic_hotness.get(topic_id)
            # sid = str(topic_id)
            # score = self.topic_hotness.get(sid)
            if score and score > 0:
                valid_topics.append(topic_id)
                weights.append(score)

        if not valid_topics:
            return None, None

        total_weight = sum(weights)
        probs = [w / total_weight for w in weights]

        selected_topic_id = np.random.choice(valid_topics, p=probs)
        selected_score = self.topic_hotness.get(selected_topic_id, 0)

        return selected_topic_id, selected_score

    # def _write_new_topic_data(self, topic_id, writer_instance):

    #         if topic_id in self.topics_written_this_run:
    #             return

    #         # print(f" 正在查找 Topic {topic_id} ...")

    #         try:
    #             with open(self.path_to_topics_all, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if row['id'] == topic_id:
    #                         writer_instance.write_new_topic(row)
    #                         # print(f" 已将新主题 {topic_id} 写入文件。")
    #                         self.topics_written_this_run.add(topic_id)
    #                         return
    #             print(f" WARNINIG：新主题 {topic_id} 在 topics_all.csv 中未找到！")

    #         except FileNotFoundError:
    #             print(f" ERROR: 找不到 'topics_all.csv' 文件于: {self.path_to_topics_all}")
    #         except Exception as e:
    #             print(f" ERROR: 遍历 'topics_all.csv' 时失败: {e}")

    def get_topic_row_for_writing(self, topic_id_str):
        """
        从 topics_all.csv 中查找一个 Topic ID 对应的完整行数据。
        """
        try:
            with open(self.path_to_topics_all, 'r', encoding='utf-8', buffering=8*1024*1024) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['id'] == topic_id_str:
                        return row # 返回字典行
            print(f" WARNING：新主题 {topic_id_str} 在 topics_all.csv 中未找到！")
            return None
        except FileNotFoundError:
            print(f" ERROR: 找不到 'topics_all.csv' 文件于: {self.path_to_topics_all}")
            return None
        except Exception as e:
            print(f" ERROR: 遍历 'topics_all.csv' 时失败: {e}")
            return None

    def _get_primary_topic(self, author_team, p_new_topic):
        anchor_subfield = self._get_subfield_mode(author_team)
        candidate_pool = None
        is_new = False

        # ---根据概率选择“桶” ---
        if random.random() < p_new_topic:
            # ---命中“新主题” ---
            if anchor_subfield:
                # 尝试从NEW中获取
                candidate_pool = self.h_new.get(anchor_subfield)
                if candidate_pool:
                    is_new = True

            if not candidate_pool and anchor_subfield:
                # print(f" Subfield '{anchor_subfield}'  中没有“新”主题。回退到“已存在”...")
                candidate_pool = self.h_exist.get(anchor_subfield)

        else:
            # --- 未命中“新主题” ---
            if anchor_subfield:
                # 尝试从Existing中获取
                candidate_pool = self.h_exist.get(anchor_subfield)

        # --- 采样 ---
        selected_topic_id = None
        selected_score = None

        if candidate_pool:
            selected_topic_id, selected_score = self._weighted_sample_from_pool(candidate_pool)

        if selected_topic_id is None:
            if anchor_subfield:
                print(f" WARNING：Subfield '{anchor_subfield}'  中所有主题均无效。回退到“全局”采样...")
            else:
                print(" WARNING：作者团队无 Subfield 。回退到“全局”采样...")

            if not self.global_topic_ids:
                print(" ERROR：全局采样池为空！")
                return None

            selected_topic_id = np.random.choice(
                self.global_topic_ids,
                p=self.global_topic_probs
            )
            selected_score = self.topic_hotness.get(selected_topic_id, 0)
            is_new = False

        # if is_new and writer_instance:
        #     self._write_new_topic_data(selected_topic_id, writer_instance)
        display_name = self.topic_name_cache.get(str(selected_topic_id), "Unknown Topic (Cache Miss)" )
        tid_str = str(selected_topic_id)
        primary_field_id = self.map_field.get(tid_str)
        if not primary_field_id:
            row = self.get_topic_row_for_writing(tid_str)
            if row and row.get('field_id'):
                primary_field_id = str(row.get('field_id')).split('/')[-1]
        selected_topic_dict = {
            "id": selected_topic_id,
            "display_name": display_name,
            "score": selected_score,
            "_subfield_id": anchor_subfield,
            "_field_id": primary_field_id
        }

        return selected_topic_dict, is_new

    def get_topics(self, author_team, p_new_topic):
            """
            返回 Topic 列表 (N=1, 2, 3)
            """
            # 确定 Topic 数量 N
            raw_n_probs = [0.1441, 0.0904, 0.7654]
            total_n_p = sum(raw_n_probs)
            n_probs = [p / total_n_p for p in raw_n_probs]
            n_topics = np.random.choice([1, 2, 3], p=n_probs)
            primary_topic, is_new_primary = self._get_primary_topic(author_team, p_new_topic)

            if not primary_topic or not primary_topic.get('id'):
                return [], False

            final_topics = [primary_topic]
            selected_ids = {primary_topic['id']}

            # 获取 Secondary Topics (副主题)
            if n_topics > 1:
                # 策略分布: 同Sub(13.86%), 同Field(23.93%), Cross(62.21%)
                # 归一化概率防止浮点误差
                raw_probs = [0.1386, 0.2393, 0.6221]
                total_p = sum(raw_probs)
                probs = [p/total_p for p in raw_probs]

                current_sub = primary_topic.get("_subfield_id")
                current_field = primary_topic.get("_field_id")

                for _ in range(n_topics - 1):
                    strategy = np.random.choice(["sub", "field", "cross"], p=probs)
                    candidate_id = None

                    if strategy == "sub" and current_sub:
                        pool = self.h_exist.get(current_sub, [])
                        if pool:
                            candidate_id = random.choice(pool)

                    elif strategy == "field" and current_field:
                        pool = self.h_field_exist.get(current_field, [])
                        if pool:
                            candidate_id, _ = self._weighted_sample_from_pool(pool)

                    if candidate_id is None:
                        if self.global_topic_ids:
                            candidate_id = np.random.choice(self.global_topic_ids, p=self.global_topic_probs)

                    if candidate_id and candidate_id not in selected_ids:
                        selected_ids.add(candidate_id)

                        if isinstance(candidate_id, str):
                            candidate_id = int(candidate_id)
                        score = self.topic_hotness.get(candidate_id, 0)
                        name = self.topic_name_cache.get(str(candidate_id), "Secondary Topic")

                        final_topics.append({
                            "id": candidate_id,
                            "display_name": name,
                            "score": score
                        })

            # 返回列表 和 是否包含新主题(只要主主题是新的就算)
            return final_topics, is_new_primary
