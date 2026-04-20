import os
import subprocess
from pathlib import Path
from tqdm import tqdm
import sys
import multiprocessing
import csv
import random
import shutil

# =========================================================
# 配置区域
# =========================================================

SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_ROOT = SCRIPT_DIR.parent
LMPLZ_PATH = os.environ.get("MAP_BENCH_LMPLZ_PATH") or shutil.which("lmplz")
BUILD_BINARY_PATH = os.environ.get("MAP_BENCH_BUILD_BINARY_PATH") or shutil.which("build_binary")

# 输入/输出目录
BASE_DATA_DIR = Path(
    os.environ.get(
        "MAP_BENCH_TRIGRAM_SOURCE_DATA_ROOT",
        str(GENERATOR_ROOT / "map-l"),
    )
)
TOPICS_CSV = BASE_DATA_DIR / "csv-files/topics.csv"

CORPUS_DIR = SCRIPT_DIR / "corpus"
MODEL_DIR = SCRIPT_DIR / "models"

NGRAM_ORDER = 5
MEMORY_PER_PROCESS_PERCENT = "20%" 
MAX_PROCESSES = 4
MIX_THRESHOLD_LINES = 1000 
AUGMENT_SIZE = 1000
topic_to_subfield_map = {}

def load_topic_map():
    """加载 Topic -> Subfield 映射，方便找‘血库’"""
    mapping = {}
    try:
        with open(TOPICS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tid = str(row.get('id', '')).split('/')[-1]
                sid = str(row.get('subfield_id', '')).split('/')[-1]
                if tid and sid:
                    mapping[tid] = sid
    except Exception as e:
        print(f"错误: 无法读取 topics.csv: {e}")
        sys.exit(1)
    return mapping

def count_lines(file_path):
    i = 0
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, _ in enumerate(f): pass
        return i + 1
    except:
        return 0

def process_single_corpus(topic_file: Path):
    topic_id = topic_file.stem.replace("topic_", "")
    model_name = f"topic_{topic_id}"
    
    arpa_path = MODEL_DIR / f"{model_name}.arpa"
    model_path = MODEL_DIR / f"{model_name}.kenlm"
    if model_path.exists() and os.path.getsize(model_path) > 1024:
        return f"SKIP: {model_name}"
    line_count = count_lines(topic_file)
    training_file = topic_file # 默认直接用原文件
    is_temp_file = False
    if line_count < MIX_THRESHOLD_LINES:
        subfield_id = topic_to_subfield_map.get(topic_id)
        subfield_file = CORPUS_DIR / f"subfield_{subfield_id}.txt"
        
        if subfield_id and subfield_file.exists():
            temp_file = MODEL_DIR / f"temp_train_{topic_id}.txt"
            
            try:
                with open(temp_file, 'w', encoding='utf-8') as out_f:
                    with open(topic_file, 'r', encoding='utf-8') as in_f:
                        shutil.copyfileobj(in_f, out_f)
                    augment_lines = []
                    with open(subfield_file, 'r', encoding='utf-8') as sub_f:
                        for _ in range(5000): # 读前5000行作为候选
                            line = sub_f.readline()
                            if not line: break
                            augment_lines.append(line)
                    if augment_lines:
                        chosen = random.sample(augment_lines, min(len(augment_lines), AUGMENT_SIZE))
                        out_f.writelines(chosen)
                
                training_file = temp_file
                is_temp_file = True
                
            except Exception as e:
                training_file = topic_file 
    if count_lines(training_file) < 5:
        if is_temp_file and training_file.exists(): os.remove(training_file)
        return f"SKIP (Too Small): {model_name}"

    try:
        # --- 2. 训练 (lmplz) ---
        train_cmd = [
            str(LMPLZ_PATH),
            "-o", str(NGRAM_ORDER),
            "-S", MEMORY_PER_PROCESS_PERCENT, 
            "--text", str(training_file),
            "--arpa", str(arpa_path),
            "--discount_fallback", # 关键：防止数据少时报错
            # "--prune", "0 0 1"     # 可选：剪枝优化，去掉频次为1的高阶gram，减小模型体积
        ]
        
        subprocess.run(train_cmd, check=True, capture_output=True, text=True)

        # --- 3. 压缩为二进制 (build_binary) ---
        build_cmd = [
            str(BUILD_BINARY_PATH),
            str(arpa_path),
            str(model_path)
        ]
        subprocess.run(build_cmd, check=True, capture_output=True, text=True)

        return f"SUCCESS: {model_name}"

    except subprocess.CalledProcessError as e:
        return f"FAILED: {model_name} | {e.stderr}"
    except Exception as e:
        return f"ERROR: {model_name} | {e}"
    finally:
        # 清理临时文件
        if arpa_path.exists(): os.remove(arpa_path)
        if is_temp_file and training_file.exists(): os.remove(training_file)

def train_models_parallel():
    # 初始化
    if not LMPLZ_PATH:
        print("错误: 未找到 KenLM 的 lmplz。请将其加入 PATH，或设置 MAP_BENCH_LMPLZ_PATH。")
        sys.exit(1)
    if not BUILD_BINARY_PATH:
        print("错误: 未找到 KenLM 的 build_binary。请将其加入 PATH，或设置 MAP_BENCH_BUILD_BINARY_PATH。")
        sys.exit(1)
        
    if not MODEL_DIR.exists(): os.makedirs(MODEL_DIR)

    # 加载映射 (主进程加载一次即可，Multiprocessing on Linux uses fork, so memory is shared)
    global topic_to_subfield_map
    topic_to_subfield_map = load_topic_map()

    # 扫描所有 Topic 文件 (不包含 Subfield 文件)
    corpus_files = sorted(list(CORPUS_DIR.glob("topic_*.txt")))
    
    print(f"找到 {len(corpus_files)} 个 Topic 待训练。")
    print(f"使用 lmplz: {LMPLZ_PATH}")
    print(f"使用 build_binary: {BUILD_BINARY_PATH}")
    print(f"策略: 行数 < {MIX_THRESHOLD_LINES} 时，混合 Subfield 数据增强。")

    with multiprocessing.Pool(processes=MAX_PROCESSES) as pool:
        results = []
        for result in tqdm(
            pool.imap_unordered(process_single_corpus, corpus_files),
            total=len(corpus_files),
            desc="并行训练中"
        ):
            results.append(result)
            
    # 统计结果
    success = sum(1 for r in results if r.startswith("SUCCESS"))
    skip = sum(1 for r in results if r.startswith("SKIP"))
    failed = sum(1 for r in results if r.startswith("FAILED") or r.startswith("ERROR"))
    
    print(f"\n训练结束: 成功 {success}, 跳过 {skip}, 失败 {failed}")
    if failed > 0:
        print("失败样本:", [r for r in results if "FAILED" in r][:5])

if __name__ == "__main__":
    train_models_parallel()
