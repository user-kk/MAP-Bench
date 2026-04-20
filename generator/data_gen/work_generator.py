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
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # .../data_gen
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)              # .../openalex_gen
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
    
    # 1. 准备模型 (保持原逻辑)
    topic_id = primary_topic.get("id") if primary_topic else 10029
    model = _load_model(topic_id, subfield_id)
    
    if not model:
        return "Placeholder Title", "Placeholder Abstract (Model Missing)"

    # 定义常量 (对应你原始代码中的约束常量)
    MIN_PUNCT_DIST = 5
    MIN_TOTAL_LEN = 5
    REAL_K = 50

    def _core_gen_loop(max_length):
        
        # 初始化状态
        state = kenlm.State()
        model.BeginSentenceWrite(state)
        
        generated_sequence = []
        words_since_last_punct = 0
        
        for i in range(max_length):
            candidate_words = []
            log_probs = []

            # 遍历全局词汇表 _TOP_K_VOCAB
            for word in _TOP_K_VOCAB:
                if word == "<s>": continue
                
                is_punct = word in PUNCTUATION_SET

                if i == 0 and is_punct:
                    continue
                if generated_sequence and (generated_sequence[-1] in PUNCTUATION_SET) and is_punct:
                    continue
                if is_punct and words_since_last_punct < MIN_PUNCT_DIST:
                    continue
                if i < MIN_TOTAL_LEN and word == "</s>":
                    continue
                if generated_sequence and word == generated_sequence[-1]:
                    continue
                if word in STOPWORDS:
                    window = generated_sequence[-3:]
                    if word in window:
                        continue
                out_state_temp = kenlm.State()
                try:
                    word_log_prob = model.score(word,state, out_state_temp)
                except AttributeError:
                    word_log_prob = model.Score(word,state, out_state_temp)
                    
                candidate_words.append(word)
                log_probs.append(word_log_prob)

            if not candidate_words:
                break
            log_probs_arr = np.array(log_probs)
            log_probs_arr = log_probs_arr - np.max(log_probs_arr) # 防止溢出
            probs_arr = 10**log_probs_arr  # KenLM 默认是 log10
            probs_sum = np.sum(probs_arr)
            
            if probs_sum == 0: break
            probs_arr = probs_arr / probs_sum
            current_k = REAL_K
            if len(probs_arr) < current_k:
                current_k = len(probs_arr)
                
            top_indices = np.argsort(probs_arr)[-current_k:]
            top_probs = probs_arr[top_indices]
            top_words = [candidate_words[idx] for idx in top_indices]
            top_probs_sum = np.sum(top_probs)
            if top_probs_sum == 0: break
            top_probs = top_probs / top_probs_sum
            try:
                next_word = np.random.choice(top_words, p=top_probs)
            except ValueError:
                next_word = "</s>"
            if next_word == "</s>":
                break
            generated_sequence.append(next_word)
            if next_word in PUNCTUATION_SET:
                words_since_last_punct = 0
            else:
                words_since_last_punct += 1
            new_state = kenlm.State()
            try:
                model.score(next_word,state,  new_state)
            except AttributeError:
                model.Score(next_word,state,  new_state)
            state = new_state
        raw_text = " ".join(generated_sequence)
        
        for p in string.punctuation:
            if p not in ['(', '[', '{']: 
                raw_text = raw_text.replace(f" {p}", p)
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
    target_total_words = _get_target_length()
    all_kws = []
    if keywords_str:
        all_kws.extend(keywords_str.replace(",", " ").split())
        
    if secondary_topics_list:
        for t in secondary_topics_list:
            t_name = t.get("display_name", "")
            all_kws.extend(t_name.replace("-", " ").split())
    core_terms = [w for w in all_kws if len(w) > 3 and w.lower() not in STOPWORDS]
    
    middle_text = ""
    if core_terms:
        bomb_length = int(target_total_words * 0.4) 
        bomb_words = []
        for _ in range(bomb_length):
            bomb_words.append(random.choice(core_terms))
        for i in range(10, bomb_length, 12):
            bomb_words[i] = bomb_words[i] + "."
            
        middle_text = " ".join(bomb_words) + "."
    else:
        middle_text = "This paper focuses on the key aspects of the domain."

    middle_word_count = len(middle_text.split())
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
    full_abstract = f"{intro_text} {middle_text} {outro_text}"
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
        # 模式 B: 使用 Faker 随机填充 (快，无语义)
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
            vec_text_raw = model.encode(combined_text) 
            if topic_id_str in topic_vectors_map:
                vec_topic_raw = np.array(topic_vectors_map[topic_id_str])
            else:
                vec_topic_raw = model.encode(topic_text)
            sec_vecs = []
            if selected_topics_list and len(selected_topics_list) > 1:
                for t in selected_topics_list[1:]:
                    tid_str = str(t.get("id"))
                    if tid_str in topic_vectors_map:
                        sec_vecs.append(np.array(topic_vectors_map[tid_str]))
                    else:
                        t_text = topic_text_map.get(tid_str, t.get("display_name", "unknown topic"))
                        sec_vecs.append(model.encode(t_text))
                    
            if sec_vecs:
                vec_sec_raw = np.mean(sec_vecs, axis=0)
            else:
                vec_sec_raw = np.random.normal(0, 0.05, size=vec_text_raw.shape)

            alpha = 0.80 
            beta  = 0.15  
            gamma = 0.05   
            
            vec_final = (alpha * vec_text_raw) + (beta * vec_topic_raw) + (gamma * vec_sec_raw)
            noise = np.random.normal(0, 0.01, size=vec_final.shape)
            vec_final = vec_final + noise
            norm = np.linalg.norm(vec_final)
            if norm > 0:
                vec_final = vec_final / norm
                
            work_vec_str = str(vec_final.tolist())
            topic_vec_str = str(vec_topic_raw.tolist()) 
            
        except Exception as e:
            print(f" ERROR: 向量多锚点平滑失败: {e}")
            work_vec_str = str([0.0] * 384)
            topic_vec_str = str([0.0] * 384)
    else:
        work_vec_str = str([0.0] * 384)
        topic_vec_str = str([0.0] * 384)
    inverted_index_data = _calculate_inverted_index(work_abstract)   
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
