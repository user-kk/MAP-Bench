from pathlib import Path
from collections import Counter
from tqdm import tqdm
import sys

# --- 配置 ---
SCRIPT_DIR = Path(__file__).resolve().parent
CORPUS_DIR = SCRIPT_DIR / "corpus"
TOP_K = 100000
GLOBAL_VOCAB_PATH = SCRIPT_DIR / "vocab.txt"
REQUIRED_TOKENS = ["</s>"] 
# ---

def create_global_vocab():
    print(f"--- 正在创建全局 Top-{TOP_K} 词汇表 ---")
    
    if not CORPUS_DIR.exists():
        print(f"错误: 语料库目录 {CORPUS_DIR} 未找到。")
        sys.exit(1)
    corpus_files = list(CORPUS_DIR.glob("topic_*.txt"))
    if not corpus_files:
        print(f"错误: 在 {CORPUS_DIR} 中未找到 topic 文件。")
        sys.exit(1)
        
    print(f"正在从 {len(corpus_files)} 个主题语料库文件中统计词频...")

    global_word_counts = Counter()

    for corpus_path in tqdm(corpus_files, desc="全局词频统计"):
        try:
            with open(corpus_path, 'r', encoding='utf-8') as f:
                for line in f:
                    words = line.strip().split()
                    if words:
                        global_word_counts.update(words)
        except Exception as e:
            print(f"警告: 处理 {corpus_path.name} 时出错: {e}")

    print(f"总共找到 {len(global_word_counts)} 个独立单词。")
    most_common_words = global_word_counts.most_common(TOP_K)
    vocab_set = {word for word, count in most_common_words}
    for token in REQUIRED_TOKENS:
        if token not in vocab_set:
            vocab_set.add(token)
    print(f"正在将 {len(vocab_set)} 个词写入到 {GLOBAL_VOCAB_PATH}...")
    try:
        with open(GLOBAL_VOCAB_PATH, 'w', encoding='utf-8') as f:
            for word in sorted(list(vocab_set)): 
                f.write(word + "\n")
        print("--- 全局词汇表创建成功！ ---")
    except Exception as e:
        print(f"错误: 写入文件 {GLOBAL_VOCAB_PATH} 失败: {e}")

if __name__ == "__main__":
    create_global_vocab()
