import csv
import json
import os
from pathlib import Path
from tqdm import tqdm
import sys
import re
import html
import string
from collections import defaultdict

# =========================================================
# 配置区域 (Configuration)
# =========================================================
NEW_LIMIT = 20 * 1024 * 1024 
csv.field_size_limit(NEW_LIMIT)

SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_ROOT = SCRIPT_DIR.parent
BASE_DATA_DIR = Path(
    os.environ.get(
        "MAP_BENCH_TRIGRAM_SOURCE_DATA_ROOT",
        str(GENERATOR_ROOT / "map-l"),
    )
)
SOURCE_DOC_FILE = BASE_DATA_DIR / "document/works_doc.csv"
SOURCE_TOPICS_FILE = BASE_DATA_DIR / "csv-files/topics.csv"
CORPUS_DIR = SCRIPT_DIR / "corpus"
SCORE_THRESHOLD = 0.5 
BATCH_SIZE = 10000 
GARBAGE_PHRASES = [
    "download this paper", "open pdf in browser", "add paper to my library",
    "share on facebook", "share on twitter", "share on linkedin", "share on reddit",
    "no accesschapter", "zip file contains", "click here to download",
    "view full text", "cited by:", "all rights reserved", "this article is available",
    "access provided by", "copyright ©", "download citation",
    "permission to reuse", "check for updates"
]

PATTERN_URL = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
PATTERN_HTML_TAG = re.compile(r'<[^>]+>')
PATTERNS_NOISE_PREFIX = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^\s*abstract\s*[:\-\.]?\s*', r'^\s*background\s*[:\-\.]?\s*',
        r'^\s*introduction\s*[:\-\.]?\s*', r'^\s*summary\s*[:\-\.]?\s*',
        r'^\s*copyright\s*[:\-\.]?\s*', r'^\s*©.*?\s*', r'^\s*\(c\).*?\s*',
        r'^\s*published by.*?\s*' 
    ]
]
PATTERN_NUM_START = re.compile(r'^\s*\d+(\.\d+)*\.?\s*')
PATTERN_SINGLE_CHAR = re.compile(r'\b(?![aiAI]\b)[a-zA-Z]\b')
PATTERN_DOT_SMART = re.compile(r'(?<!\d)\.(?!\d)')
PATTERN_OTHER_PUNCT = re.compile(r'([,;!?()])')
PATTERN_HYPHEN = re.compile(r'-+')
PATTERN_REPEAT_PUNCT_STRICT = re.compile(r'([.,;!?\-])(?:[\s]*\1)+')
PATTERN_WHITESPACE = re.compile(r'\s+')

def clean_abstract_text(text):
    if not text: return None
    text = text.lower()
    for garbage in GARBAGE_PHRASES:
        if garbage in text: return None
    text = html.unescape(text)
    text = PATTERN_URL.sub(' ', text)
    text = PATTERN_HTML_TAG.sub(' ', text)
    text = text.replace('\n', ' ').replace('\r', ' ')
    for pattern in PATTERNS_NOISE_PREFIX:
        text = pattern.sub('', text)
    text = PATTERN_NUM_START.sub('', text)
    text = PATTERN_HYPHEN.sub(' ', text)
    text = PATTERN_SINGLE_CHAR.sub(' ', text)
    text = PATTERN_DOT_SMART.sub(' . ', text)
    text = PATTERN_OTHER_PUNCT.sub(r' \1 ', text)
    text = PATTERN_REPEAT_PUNCT_STRICT.sub(r'\1', text)
    text = PATTERN_WHITESPACE.sub(' ', text).strip()
    text = text.lstrip(string.punctuation + " ")
    if len(text) < 50: return None
    if len(text.split()) < 5: return None
    return text

def load_topic_metadata_and_init_files():

    if os.path.exists(CORPUS_DIR):
        import shutil
        shutil.rmtree(CORPUS_DIR)
    os.makedirs(CORPUS_DIR)
    
    mapping = {}
    count = 0
    
    try:
        with open(SOURCE_TOPICS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in tqdm(reader, desc="Init Topics"):
                tid = str(row.get('id', '')).split('/')[-1]
                sid = str(row.get('subfield_id', '')).split('/')[-1]
                
                if tid and sid:
                    mapping[tid] = sid
                    d_name = row.get('display_name', '').strip()
                    desc = row.get('description', '').strip()
                    keywords = row.get('keywords', '').replace(',', ' ').strip() # 去逗号
                    components = []
                    if d_name: components.append(d_name)
                    if desc: components.append(desc)
                    if keywords: components.append(keywords)
                    
                    if components:
                        seed_sentence = ". ".join(components) + "."
                        weighted_text = (seed_sentence + " ") * 50
                        with open(CORPUS_DIR / f"topic_{tid}.txt", 'w', encoding='utf-8') as tf:
                            tf.write(weighted_text + "\n")
                    
                    count += 1
                    
    except Exception as e:
        print(f"错误: 读取 topics.csv 失败: {e}")
        sys.exit(1)
        
    print(f"已初始化 {count} 个 Topic 文件 (含语义锚点)。")
    return mapping

def flush_buffers(buffer_dict):
    if not buffer_dict: return
    for file_path, lines in buffer_dict.items():
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            print(f"写入失败 {file_path}: {e}")
    buffer_dict.clear()

def extract_corpus_from_csv():
    topic_subfield_map = load_topic_metadata_and_init_files()
    print(f"开始处理源文档: {SOURCE_DOC_FILE}")
    stats = {
        "Rows": 0, "Valid": 0, "Garbage": 0, "Not_English": 0
    }
    write_buffer = defaultdict(list)
    try:
        with open(SOURCE_DOC_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            with tqdm(reader, unit=' rows', desc="提取语料") as pbar:
                for row in pbar:
                    stats["Rows"] += 1
                    if stats["Rows"] % BATCH_SIZE == 0:
                        flush_buffers(write_buffer)
                        pbar.set_postfix({"Valid": stats["Valid"]})
                    doc_json = row.get("doc")
                    if not doc_json: continue 
                    try:
                        doc_data = json.loads(doc_json)
                        if doc_data.get("language") != "en":
                            stats["Not_English"] += 1
                            continue
                        raw_abstract = doc_data.get("abstract")
                        if not raw_abstract: continue
                        topics = doc_data.get("topics", [])
                        if not topics: continue
                        cleaned_abstract = clean_abstract_text(raw_abstract)
                        if cleaned_abstract is None:
                            stats["Garbage"] += 1
                            continue
                        has_valid_topic = False
                        written_subfields_for_this_doc = set()
                        for t in topics:
                            tid = str(t.get("id", "")).split('/')[-1]
                            score = float(t.get("score", 0))
                            if tid and score >= SCORE_THRESHOLD:
                                has_valid_topic = True
                                write_buffer[CORPUS_DIR / f"topic_{tid}.txt"].append(cleaned_abstract)
                                sid = topic_subfield_map.get(tid)
                                if sid and sid not in written_subfields_for_this_doc:
                                    write_buffer[CORPUS_DIR / f"subfield_{sid}.txt"].append(cleaned_abstract)
                                    written_subfields_for_this_doc.add(sid)
                        
                        if has_valid_topic:
                            stats["Valid"] += 1

                    except Exception:
                        continue
            
            flush_buffers(write_buffer)

    except FileNotFoundError:
        print(f"ERROR：找不到源文件 {SOURCE_DOC_FILE}")
        sys.exit(1)

    print("\n--- 提取完成 ---")
    print(f"总行数: {stats['Rows']}")
    print(f"有效摘要: {stats['Valid']}")
    print(f"跳过(非英文): {stats['Not_English']}")
    print(f"跳过(垃圾/太短): {stats['Garbage']}")

if __name__ == "__main__":
    extract_corpus_from_csv()
