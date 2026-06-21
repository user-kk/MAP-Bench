# data_gen/work_generator.py
import random
import csv
import numpy as np
import json
from itertools import combinations
import kenlm
import os
import sys
import datetime
import string
from collections import OrderedDict
_CURRENT_MAX_WORK_ID = 0
from sentence_transformers import SentenceTransformer
from faker import Faker
fake = Faker()
_EMBEDDING_MODEL = None
_EMBEDDING_MODEL_PATH = None
TEMPLATES_CITATION_REF = [
    "Building upon recent works on {keyword}, we propose a robust solution that specifically targets the limitations observed in existing {keyword} frameworks.",
    "Unlike previous studies focusing primarily on conventional {keyword}, our method addresses the scalability issue inherent in large-scale {keyword} deployments.",
    "Extensive research in {keyword} has laid the groundwork for this analysis. By leveraging the principles of {keyword}, we formulate a novel architecture.",
    "Following the established protocols in {keyword} research, we validated our model against standard benchmarks utilized in {keyword} evaluation."
]

TEMPLATES_CROSS_DOMAIN = [
    "Integrating concepts from {name}, this study explores new avenues for optimization, bridging {name} with our primary focus.",
    "By applying methodologies typically seen in {name}, we achieve significant improvements over traditional baseline techniques.",
    "In the context of {name}, these findings offer a novel perspective that enhances the broader applicability of our framework."
]
STOPWORDS = {
    'the', 'a', 'an', 'of', 'to', 'in', 'and', 'is', 'for',
    'that', 'with', 'on', 'as', 'by', 'this', 'are', 'it'
}
PUNCTUATION_SET = set(string.punctuation)
def initialize_embedding_model(model_path):
    """主进程调用：设置模型路径（不加载）"""
    global _EMBEDDING_MODEL_PATH
    _EMBEDDING_MODEL_PATH = model_path

def _get_embedding_model():
    """Worker 内部调用：懒加载单例模式"""
    global _EMBEDDING_MODEL, _EMBEDDING_MODEL_PATH
    if _EMBEDDING_MODEL is None:
        if _EMBEDDING_MODEL_PATH and os.path.exists(_EMBEDDING_MODEL_PATH) and SentenceTransformer:
            try:
                # 使用 CPU 加载，避免多进程 CUDA 冲突
                _EMBEDDING_MODEL = SentenceTransformer(_EMBEDDING_MODEL_PATH, device='cpu')
            except Exception as e:
                print(f" ERROR: 模型加载失败: {e}")
                _EMBEDDING_MODEL = "FAILED"
        else:
            _EMBEDDING_MODEL = "FAILED"
    return _EMBEDDING_MODEL

def _generate_vector_str(text):
    """通用向量生成函数：返回 '[0.1, ...]' 字符串"""
    model = _get_embedding_model()
    if not text or model == "FAILED" or model is None:
        return str([0.0] * 384) # 失败返回零向量
    try:
        embedding = model.encode(text)
        return str(embedding.tolist())
    except Exception as e:
        return str([0.0] * 384)

def _calculate_inverted_index(abstract_text):
    """
    计算摘要的反向索引。
    将每个单词（token）映射到它在 token 流中的位置
    """
    if not abstract_text:
        return {}

    inverted_index = {}
    tokens = abstract_text.split()

    for index, token in enumerate(tokens):
        token_str = str(token)

        if token_str not in inverted_index:
            inverted_index[token_str] = []

        inverted_index[token_str].append(index)

    return inverted_index
def initialize_work_id_counter(max_id_from_sf1):

    global _CURRENT_MAX_WORK_ID
    if max_id_from_sf1 and max_id_from_sf1 > 0:
        _CURRENT_MAX_WORK_ID = max_id_from_sf1
    else:
        _CURRENT_MAX_WORK_ID = 4500000000
    # print(f"--- Work ID 已初始化，起始点: {_CURRENT_MAX_WORK_ID}")

def get_new_work_id():
    """
    生成一个全局唯一的 Work ID (递增)。
    """
    global _CURRENT_MAX_WORK_ID
    _CURRENT_MAX_WORK_ID += 1
    return _CURRENT_MAX_WORK_ID

class Samplers:
    """存储和使用 'type' 和 'language' 的采样器"""
    def __init__(self, type_dist_rules, lang_dist_rules):

        # Type Sampler
        if not type_dist_rules:
            self.type_keys = ["article"]
            self.type_probs = [1.0]
        else:
            self.type_keys = list(type_dist_rules.keys())
            self.type_probs = list(type_dist_rules.values())

        # Language Sampler
        if not lang_dist_rules:
            self.lang_keys = ["en"]
            self.lang_probs = [1.0]
        else:
            self.lang_keys = list(lang_dist_rules.keys())
            self.lang_probs = list(lang_dist_rules.values())

    def sample_type(self):
        return np.random.choice(self.type_keys, p=self.type_probs)

    def sample_language(self):
        lang = np.random.choice(self.lang_keys, p=self.lang_probs)
        return "en" if lang == "other" else lang

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
except NameError:
    SCRIPT_DIR = os.getcwd()
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
NGRAM_DIR = os.environ.get(
    "MAP_BENCH_NGRAM_DIR",
    os.path.join(PROJECT_ROOT, "TRIGRAM_TRAIN"),
)
KENLM_MODEL_DIR = os.environ.get(
    "MAP_BENCH_NGRAM_MODEL_DIR",
    os.path.join(NGRAM_DIR, "models"),
)
TOP_K_VOCAB_PATH = os.environ.get(
    "MAP_BENCH_NGRAM_VOCAB_PATH",
    os.path.join(NGRAM_DIR, "vocab.txt"),
)
_MODEL_CACHE = {}
_VOCAB_CACHE = None

def _load_global_vocab(path):
    """加载一次 K-Top 词汇表"""
    global _VOCAB_CACHE
    if _VOCAB_CACHE is not None:
        return _VOCAB_CACHE

    # print(f" 正在加载全局 Top-K 词汇表: {path}")
    vocab = []
    try:
        with open(path, 'r', encoding='utf-8', buffering=8*1024*1024) as f:
            for line in f:
                word = line.strip()
                if word:
                    vocab.append(word)

        # 确保 BOS/EOS 标记存在
        if "</s>" not in vocab:
            vocab.append("</s>")
        if "<s>" not in vocab:
            vocab.append("<s>")
        # print(f" 词汇表加载完毕 (K={len(vocab)})")
        _VOCAB_CACHE = vocab
        return vocab
    except Exception as e:
        print(f" ERROR: 无法加载 K-Top 词汇表: {e}")
        _VOCAB_CACHE = ["this", "paper", "is", "a", "test", "</s>", "<s>"] # 备用
        return _VOCAB_CACHE

def _load_model(topic_id, subfield_id=None):
    """按需加载并缓存 .kenlm 模型"""
    # 检查缓存
    if topic_id in _MODEL_CACHE:
        return _MODEL_CACHE[topic_id]

    topic_model_path = os.path.join(KENLM_MODEL_DIR, f"topic_{topic_id}.kenlm")

    if os.path.exists(topic_model_path):
        try:
            model = kenlm.Model(topic_model_path)
            _MODEL_CACHE[topic_id] = model
            return model
        except Exception as e:
            print(f" ERROR: Topic 模型损坏 {topic_id}: {e}")

    if subfield_id:
        cache_key = f"subfield_{subfield_id}"
        if cache_key in _MODEL_CACHE:
            return _MODEL_CACHE[cache_key]

        subfield_model_path = os.path.join(KENLM_MODEL_DIR, f"subfield_{subfield_id}.kenlm")

        if os.path.exists(subfield_model_path):
            try:
                model = kenlm.Model(subfield_model_path)
                _MODEL_CACHE[cache_key] = model
                _MODEL_CACHE[topic_id] = model
                return model
            except Exception as e:
                print(f" ERROR: Subfield 模型损坏 {subfield_id}: {e}")

    _MODEL_CACHE[topic_id] = None
    return None
_TOP_K_VOCAB = _load_global_vocab(TOP_K_VOCAB_PATH)
_TOP_K_VOCAB_NO_BOS = [word for word in _TOP_K_VOCAB if word != "<s>"]
_TOP_K_VOCAB_IS_PUNCT = [word in PUNCTUATION_SET for word in _TOP_K_VOCAB_NO_BOS]
_TOP_K_VOCAB_IS_STOPWORD = [word in STOPWORDS for word in _TOP_K_VOCAB_NO_BOS]
_TEXT_TOPK_CACHE_ENABLED = os.environ.get("MAP_BENCH_P2_CACHE", "0") == "1"
_TEXT_TOPK_PROBE_ENABLED = os.environ.get("MAP_BENCH_P2_PROBE", "0") == "1"
_TEXT_TOPK_CACHE_SIZE = max(0, int(os.environ.get("MAP_BENCH_P2_CACHE_SIZE", "5000")))
_TEXT_TOPK_CACHE = OrderedDict()
_TEXT_TOPK_CACHE_STATS = {"lookups": 0, "hits": 0, "misses": 0, "stores": 0}
_TEXT_SCORE_CACHE_ENABLED = os.environ.get("MAP_BENCH_P4_SCORE_CACHE", "0") == "1"
_TEXT_SCORE_CACHE_SIZE = max(0, int(os.environ.get("MAP_BENCH_P4_SCORE_CACHE_SIZE", "64")))
_TEXT_SCORE_CACHE = OrderedDict()
_TEXT_SCORE_CACHE_STATS = {"lookups": 0, "hits": 0, "misses": 0, "builds": 0}

def get_text_cache_stats():
    return dict(_TEXT_TOPK_CACHE_STATS)

def get_text_score_cache_stats():
    stats = dict(_TEXT_SCORE_CACHE_STATS)
    stats["cached_models"] = len(_TEXT_SCORE_CACHE)
    stats["cache_size"] = _TEXT_SCORE_CACHE_SIZE
    return stats

def _can_use_text_score_cache(score_func):
    return getattr(score_func, "__name__", "") == "score"

def _get_text_score_cache(model, score_func):
    if not _TEXT_SCORE_CACHE_ENABLED:
        return None
    if _TEXT_SCORE_CACHE_SIZE <= 0:
        return None
    if not _can_use_text_score_cache(score_func):
        return None

    _TEXT_SCORE_CACHE_STATS["lookups"] += 1
    cache_key = id(model)
    cached = _TEXT_SCORE_CACHE.get(cache_key)
    if cached is not None:
        _TEXT_SCORE_CACHE_STATS["hits"] += 1
        _TEXT_SCORE_CACHE.move_to_end(cache_key)
        return cached

    _TEXT_SCORE_CACHE_STATS["misses"] += 1
    dummy_state = kenlm.State()
    dummy_out_state = kenlm.State()
    scores = np.empty(len(_TOP_K_VOCAB_NO_BOS), dtype=np.float64)
    for idx, word in enumerate(_TOP_K_VOCAB_NO_BOS):
        scores[idx] = score_func(word, dummy_state, dummy_out_state)

    _TEXT_SCORE_CACHE[cache_key] = scores
    _TEXT_SCORE_CACHE.move_to_end(cache_key)
    _TEXT_SCORE_CACHE_STATS["builds"] += 1
    while len(_TEXT_SCORE_CACHE) > _TEXT_SCORE_CACHE_SIZE:
        _TEXT_SCORE_CACHE.popitem(last=False)
    return scores

def _make_text_topk_cache_key(
    model_key,
    generated_sequence,
    position,
    min_total_len,
    min_punct_dist,
    words_since_last_punct,
    last_word_is_punct,
    recent_window,
):
    recent_stopwords = tuple(sorted(word for word in recent_window if word in STOPWORDS))
    return (
        model_key,
        tuple(generated_sequence[-2:]),
        position == 0,
        position < min_total_len,
        min(words_since_last_punct, min_punct_dist),
        last_word_is_punct,
        recent_stopwords,
    )

def _get_cached_text_topk(cache_key):
    if not (_TEXT_TOPK_CACHE_ENABLED or _TEXT_TOPK_PROBE_ENABLED):
        return None
    if _TEXT_TOPK_CACHE_SIZE <= 0:
        return None

    _TEXT_TOPK_CACHE_STATS["lookups"] += 1
    cached = _TEXT_TOPK_CACHE.get(cache_key)
    if cached is None:
        _TEXT_TOPK_CACHE_STATS["misses"] += 1
        return None

    _TEXT_TOPK_CACHE_STATS["hits"] += 1
    _TEXT_TOPK_CACHE.move_to_end(cache_key)
    if _TEXT_TOPK_CACHE_ENABLED:
        return cached
    return None

def _store_text_topk_cache(cache_key, top_words, top_probs):
    if not (_TEXT_TOPK_CACHE_ENABLED or _TEXT_TOPK_PROBE_ENABLED):
        return
    if _TEXT_TOPK_CACHE_SIZE <= 0:
        return

    _TEXT_TOPK_CACHE[cache_key] = (top_words, top_probs)
    _TEXT_TOPK_CACHE.move_to_end(cache_key)
    _TEXT_TOPK_CACHE_STATS["stores"] += 1
    while len(_TEXT_TOPK_CACHE) > _TEXT_TOPK_CACHE_SIZE:
        _TEXT_TOPK_CACHE.popitem(last=False)

def generate_fake_text_func():
    """
    使用 Faker 生成随机的标题和摘要
    """
    # 生成一个 6-12 个单词的句子作为标题
    title = fake.sentence(nb_words=10, variable_nb_words=True)
    title = title.rstrip('.')

    # 生成一段文本作为摘要
    abstract = fake.text(max_nb_chars=800)

    return title, abstract

def text_generator_func(primary_topic, secondary_topics_list=None, keywords_str=None, subfield_id=None):

    # 准备文本模型
    topic_id = primary_topic.get("id") if primary_topic else 10029
    model_key = str(topic_id)
    model = _load_model(topic_id, subfield_id)

    if not model:
        return "Placeholder Title", "Placeholder Abstract (Model Missing)"

    # 文本生成约束
    MIN_PUNCT_DIST = 5
    MIN_TOTAL_LEN = 5
    REAL_K = 50

    def _core_gen_loop(max_length):
        score_func = getattr(model, "score", None)
        if score_func is None:
            score_func = model.Score
        score_cache = _get_text_score_cache(model, score_func)

        # 初始化 KenLM 状态
        state = kenlm.State()
        model.BeginSentenceWrite(state)

        generated_sequence = []
        words_since_last_punct = 0

        # 生成循环
        for i in range(max_length):
            candidate_words = []
            log_probs = []
            has_generated_words = bool(generated_sequence)
            last_word = generated_sequence[-1] if has_generated_words else None
            last_word_is_punct = last_word in PUNCTUATION_SET if has_generated_words else False
            recent_window = set(generated_sequence[-3:]) if has_generated_words else set()
            cache_key = _make_text_topk_cache_key(
                model_key,
                generated_sequence,
                i,
                MIN_TOTAL_LEN,
                MIN_PUNCT_DIST,
                words_since_last_punct,
                last_word_is_punct,
                recent_window,
            )
            cached_topk = _get_cached_text_topk(cache_key)

            if cached_topk is not None:
                top_words, top_probs = cached_topk
            else:
                candidate_words = []
                log_probs = []

                # 遍历全局词汇表 _TOP_K_VOCAB（静态属性已预计算，避免内层重复判断）
                out_state_temp = kenlm.State() if score_cache is None else None
                for vocab_idx, (word, is_punct, is_stopword) in enumerate(zip(
                    _TOP_K_VOCAB_NO_BOS,
                    _TOP_K_VOCAB_IS_PUNCT,
                    _TOP_K_VOCAB_IS_STOPWORD,
                )):

                    # 约束过滤
                    # A. 首词禁令：生成的第一个词不能是标点
                    if i == 0 and is_punct:
                        continue

                    # B. 连击禁令：如果上一个词是标点，当前词不能是标点
                    if last_word_is_punct and is_punct:
                        continue

                    # C. 标点距离限制：距离上一个标点必须足够远
                    if is_punct and words_since_last_punct < MIN_PUNCT_DIST:
                        continue

                    # D. 长度惩罚：如果句子太短，禁止生成结束符
                    if i < MIN_TOTAL_LEN and word == "</s>":
                        continue

                    # E. 相邻重复禁令：禁止 "system system"
                    if has_generated_words and word == last_word:
                        continue

                    # F. 高频词距离限制：禁止 "the ... the" 挨得太近 (窗口大小=3)
                    if is_stopword and word in recent_window:
                        continue

                    # --- 计算得分 ---
                    if score_cache is not None:
                        word_log_prob = score_cache[vocab_idx]
                    else:
                        word_log_prob = score_func(word, state, out_state_temp)

                    candidate_words.append(word)
                    log_probs.append(word_log_prob)

                # 容错：如果所有词都被过滤掉了
                if not candidate_words:
                    break

                # 4. Top-K 截断 (K=50)
                log_probs_arr = np.asarray(log_probs, dtype=np.float64)
                current_k = REAL_K
                if len(log_probs_arr) < current_k:
                    current_k = len(log_probs_arr)

                top_indices = np.argpartition(log_probs_arr, -current_k)[-current_k:]
                top_log_probs = log_probs_arr[top_indices]
                top_log_probs = top_log_probs - np.max(top_log_probs)
                top_probs = 10**top_log_probs  # KenLM 默认是 log10
                top_words = [candidate_words[idx] for idx in top_indices]

                # 重新归一化
                top_probs_sum = np.sum(top_probs)
                if top_probs_sum == 0: break
                top_probs = top_probs / top_probs_sum
                _store_text_topk_cache(cache_key, top_words, top_probs)

            # 6. 采样
            try:
                next_word = np.random.choice(top_words, p=top_probs)
            except ValueError:
                next_word = "</s>"

            # 7. 终止检查
            if next_word == "</s>":
                break

            generated_sequence.append(next_word)

            # 8. 更新计数器
            if next_word in PUNCTUATION_SET:
                words_since_last_punct = 0
            else:
                words_since_last_punct += 1

            # 9. 更新状态
            new_state = kenlm.State()
            score_func(next_word, state, new_state)
            state = new_state
        # 后处理文本片段
        raw_text = " ".join(generated_sequence)

        # 修正标点前的空格 ( "word ." -> "word." )
        for p in string.punctuation:
            if p not in ['(', '[', '{']:
                raw_text = raw_text.replace(f" {p}", p)

        # 修复 HTML 实体
        raw_text = raw_text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

        if raw_text:
            raw_text = raw_text[0].upper() + raw_text[1:]

        return raw_text
    def _get_target_length():
        """
        基于真实数据统计: Mean=175.71, StdDev=181.32
        使用截断正态分布生成合理的目标长度。
        """
        mu = 175.71
        sigma = 181.32
        # min_len = 60   # 最小长度
        # max_len = 600  # 最大长度 (虽然真实有更长的，但600词已经足够涵盖大多数情况)

        # while True:
        #     val = random.normalvariate(mu, sigma)
        #     if min_len <= val <= max_len:
        #         return int(val)
        val = random.normalvariate(mu, sigma)
        return int(max(60, min(val, 600)))
    # 组装摘要结构
    target_total_words = _get_target_length()

    # 收集核心词汇
    all_kws = []
    if keywords_str:
        all_kws.extend(keywords_str.replace(",", " ").split())

    if secondary_topics_list:
        for t in secondary_topics_list:
            t_name = t.get("display_name", "")
            all_kws.extend(t_name.replace("-", " ").split())

    # 过滤短词和停用词
    core_terms = [w for w in all_kws if len(w) > 3 and w.lower() not in STOPWORDS]

    middle_text = ""
    if core_terms:
        # 构建关键词密集片段
        bomb_length = int(target_total_words * 0.4)
        bomb_words = []

        # 随机抽取核心词汇进行堆叠
        for _ in range(bomb_length):
            bomb_words.append(random.choice(core_terms))

        # 每隔 8 到 12 个词，强行加一个句号。
        for i in range(10, bomb_length, 12):
            bomb_words[i] = bomb_words[i] + "."

        middle_text = " ".join(bomb_words) + "."
    else:
        middle_text = "This paper focuses on the key aspects of the domain."

    middle_word_count = len(middle_text.split())

    # 其余篇幅由 KenLM 生成
    remaining_words = target_total_words - middle_word_count
    if remaining_words < 20:
        remaining_words = 20

    intro_len_target = int(remaining_words * 0.5)
    outro_len_target = remaining_words - intro_len_target

    intro_text = _core_gen_loop(intro_len_target)
    if intro_text and not intro_text.strip().endswith('.'):
        intro_text += "."

    outro_text = _core_gen_loop(outro_len_target)
    if outro_text and not outro_text.endswith('.'):
        outro_text += "."

    # 组装最终文本
    full_abstract = f"{intro_text} {middle_text} {outro_text}"

    # 生成标题
    if core_terms:
        title_len = random.randint(5, 10)
        title_words = random.choices(core_terms, k=title_len)
        title = " ".join(title_words).title()
    else:
        title = "A Study on " + primary_topic.get('display_name', 'Unknown')

    return title, full_abstract

def _build_authorships(author_team, core_team_ids):
    """
    构建 doc.authorships 数组
    """
    authorships = []

    core_id_set_str = {str(cid) for cid in core_team_ids}

    # 拆分团队
    core_authors = []
    other_authors = []
    for author in author_team:
        if str(author["id"]) in core_id_set_str:
            core_authors.append(author)
        else:
            other_authors.append(author)

    # 将所有核心作者 (共同第一作者)放进去
    for author in core_authors:
        authorships.append({
            "author_position": "first",
            "author": {
                "id": author["id"],
                "display_name": author.get("display_name"),
                "institution": {"id": author.get("institution_id"),"display_name": author.get("institution_display_name")}
            }
        })

    # 添加所有“其他作者” (middle/last)
    total_remaining = len(other_authors)
    for i, author in enumerate(other_authors):
        if i == 0 and not core_authors:
            pos = "first"
        elif i == total_remaining - 1:
             pos = "last"
        else:
             pos = "middle"

        authorships.append({
            "author_position": pos,
            "author": {
                "id": author["id"],
                "display_name": author.get("display_name"),
                "institution": {"id": author.get("institution_id")}
            }
        })

    return authorships

def _build_author_author_edges(author_team, new_work_id, current_year):
    """构建 author-author 合作边"""
    edges = []

    if len(author_team) < 2:
        return []

    for author_a, author_b in combinations(author_team, 2):
        id_a = author_a["id"]
        id_b = author_b["id"]
        if id_a is None or id_b is None:
            continue

        # 强制转换为字符串比较大小，避免 str 和 int 报错
        if str(id_a) < str(id_b):
            start_id, end_id = id_a, id_b
        else:
            start_id, end_id = id_b, id_a

        properties = {
            "cnt": 1,
            "list": [{"year": current_year, "work_id": new_work_id}]
        }
        edges.append({
            "startid": start_id,
            "endid": end_id,
            "properties": properties
        })
    return edges


# --- 主函数 ---

def generate_work_package(
    new_work_id,
    current_year,
    author_team,
    core_team_ids,
    selected_topics_list,
    citations_list,
    samplers,
    topic_text_map,
    topic_subfield_map,
    topic_vectors_map={},
    use_complex_text_gen=True
):
    """
    组装新文章数据
    """

    work_type = samplers.sample_type()
    work_lang = samplers.sample_language()
    primary_topic = selected_topics_list[0]
    if use_complex_text_gen:
        # 模式 A: 使用 KenLM 生成 (慢，有统计规律)
        topic_id_str = str(primary_topic.get("id"))
        subfield_id = topic_subfield_map.get(topic_id_str)
        kw_str = topic_text_map.get(topic_id_str, primary_topic.get("display_name"))
        work_title, work_abstract = text_generator_func(
            primary_topic=primary_topic,
            secondary_topics_list=selected_topics_list, # 传入完整列表
            keywords_str=kw_str,
            subfield_id=subfield_id
        )
    else:
        # 使用 Faker 生成占位文本
        work_title, work_abstract = generate_fake_text_func()
        # base_title, base_abs = generate_fake_text_func()
        # t_name = primary_topic.get("display_name", "General")
        # work_abstract = f"{base_abs} This work focuses on {t_name}."
        # work_title = base_title

    # work_title, work_abstract = text_generator_func(selected_topic)
    # combined_text = f"{work_title} {work_abstract}"
    # work_vec_str = _generate_vector_str(combined_text)
    # topic_id_str = str(primary_topic.get("id"))
    # topic_text = topic_text_map.get(topic_id_str)
    # if not topic_text:
    #     topic_text = primary_topic.get("display_name", "unknown topic")

    # topic_vec_str = _generate_vector_str(topic_text)
    combined_text = f"{work_title} {work_abstract}"
    topic_id_str = str(primary_topic.get("id"))
    topic_text = topic_text_map.get(topic_id_str, primary_topic.get("display_name", "unknown topic"))

    model = _get_embedding_model()
    if model != "FAILED" and model is not None:
        try:
            # 文本向量由模型生成
            vec_text_raw = model.encode(combined_text)

            # 优先使用预计算主主题向量
            if topic_id_str in topic_vectors_map:
                vec_topic_raw = np.array(topic_vectors_map[topic_id_str])
            else:
                vec_topic_raw = model.encode(topic_text)

            # 合并副主题向量
            sec_vecs = []
            if selected_topics_list and len(selected_topics_list) > 1:
                for t in selected_topics_list[1:]:
                    tid_str = str(t.get("id"))
                    if tid_str in topic_vectors_map:
                        sec_vecs.append(np.array(topic_vectors_map[tid_str]))
                    else:
                        # 未命中预计算向量时按文本编码
                        t_text = topic_text_map.get(tid_str, t.get("display_name", "unknown topic"))
                        sec_vecs.append(model.encode(t_text))

            if sec_vecs:
                vec_sec_raw = np.mean(sec_vecs, axis=0)
            else:
                # 无副主题时加入小幅随机扰动
                vec_sec_raw = np.random.normal(0, 0.05, size=vec_text_raw.shape)

            # 多重加权平滑
            alpha = 0.80   # 文本本体保留 80% 个性
            beta  = 0.15   # 修正引文相似度 (向主领域靠拢 15%)
            gamma = 0.05   # 撑开 LID 维度 (向副主题拉扯 5%)

            vec_final = (alpha * vec_text_raw) + (beta * vec_topic_raw) + (gamma * vec_sec_raw)

            # 5. 加入微量高斯底噪修复 LID 跌落
            noise = np.random.normal(0, 0.01, size=vec_final.shape)
            vec_final = vec_final + noise

            # 6. L2 归一化 (保证落在单位球面上，使 Cosine Similarity 准确)
            norm = np.linalg.norm(vec_final)
            if norm > 0:
                vec_final = vec_final / norm

            work_vec_str = str(vec_final.tolist())
            topic_vec_str = str(vec_topic_raw.tolist()) # 保留主主题的纯净向量用于落库

        except Exception as e:
            print(f" ERROR: 向量多锚点平滑失败: {e}")
            work_vec_str = str([0.0] * 384)
            topic_vec_str = str([0.0] * 384)
    else:
        # 模型加载失败的保底
        work_vec_str = str([0.0] * 384)
        topic_vec_str = str([0.0] * 384)
    inverted_index_data = _calculate_inverted_index(work_abstract)
    # work_title = None
    # work_abstract = None
    # inverted_index_data = {}

    try:
        start_of_year = datetime.date(current_year, 1, 1)
        random_day_offset = random.randint(0, 364)
        random_date = start_of_year + datetime.timedelta(days=random_day_offset)
        new_publication_date = random_date.strftime("%Y-%m-%d")
    except ValueError:
        new_publication_date = f"{current_year}-01-01"

    # 生成 fake DOI
    part1 = random.randint(1000, 9999)
    part2 = random.randint(10000, 99999)
    part3 = random.randint(10000, 99999)
    fake_doi = f"https://doi.org/10.{part1}/{part2}.{current_year}.{part3}"

    # 生成 doc 属性
    new_volume = str(random.randint(1, 10))
    new_issue = str(random.randint(1, 10))
    new_first_page = str(random.randint(1, 1000))
    new_last_page = str(int(new_first_page) + random.randint(5, 20))


    # 过滤自引用
    try:
        citations_list_filtered = [c_id for c_id in citations_list if int(c_id) != new_work_id]
    except Exception as e:
        print(f" WARNING：过滤自引用失败: {e}")
        citations_list_filtered = citations_list

    # works_new.csv
    work_relation = {
        "id": new_work_id, "doi": fake_doi, "title": work_title, "display_name": work_title,
        "publication_year": current_year, "publication_date": new_publication_date,
        "type": work_type, "cited_by_count": 0, "is_retracted": False,
        "is_paratext": False,
        "cited_by_api_url": f"https://api.openalex.org/works?filter=cites:W{new_work_id}",
        "language": work_lang
    }

    # works_doc_new.csv
    authorships = _build_authorships(author_team, core_team_ids)
    doc_topics_list = []
    for t in selected_topics_list:
        doc_topics_list.append({
            "id": t.get("id"),
            "display_name": t.get("display_name"),
            "score": t.get("score")
        })
    work_doc = {
        "id": new_work_id,
        "doc": {
            "language": work_lang, "abstract": work_abstract,
            "volume": new_volume, "issue": new_issue, "first_page": new_first_page, "last_page": new_last_page,
            "authorships": authorships,
            "topics": doc_topics_list,
            "abstract_inverted_index": inverted_index_data
        }
    }

    # works_v_new.csv
    work_vertex = {
        "id": new_work_id,
        "properties": {
            "title": work_title, "publication_year": current_year,
            "publication_date": new_publication_date, "type": work_type,
            "cited_by_count": 0, "is_retracted": False, "is_paratext": False
        }
    }

    # work_author_e_new.csv
    work_author_edges = []
    for authorship in authorships:
        work_author_edges.append({
            "startid": new_work_id,
            "endid": authorship["author"]["id"],
            "properties": {"author_position": authorship["author_position"]}
        })

    # work_topic_e_new.csv
    work_topic_edges = []
    for t in selected_topics_list:
        work_topic_edges.append({
            "startid": new_work_id,
            "endid": t.get("id"),
            "properties": {"score": t.get("score")}
        })

    # work_referenced_work_e_new.csv
    work_ref_edges = []
    for cited_id in citations_list_filtered:
        work_ref_edges.append({
            "startid": new_work_id,
            "endid": cited_id,
            "properties": {}
        })

    # author_author_e_new.csv
    author_author_edges = _build_author_author_edges(author_team, new_work_id, current_year)

    #work_vec
    work_vector_data = {
        "id": new_work_id,
        "doi": fake_doi,
        "vec": work_vec_str
    }
    return {
        "work_relation": work_relation, "work_doc": work_doc, "work_vertex": work_vertex,
        "work_author_edges": work_author_edges, "work_topic_edges": work_topic_edges,
        "work_ref_edges": work_ref_edges, "author_author_edges": author_author_edges,
        "work_vector": work_vector_data,
        "topic_vector_str": topic_vec_str
    }
