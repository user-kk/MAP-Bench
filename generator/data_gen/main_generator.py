import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
import sys
import json
from tqdm import tqdm
import subprocess
import multiprocessing
import random
import time
import csv
import numpy as np
import incremental_calculator   #增量计算器
import data_writer        #数据写入本地
import author_selector   # 作者选择模块
import author_generate   # 作者生成模块
import topic_selector   #主题选择模块
import citation_selector #引文选择模块
# import work_generator
import annual_updater
USE_COMPLEX_TEXT = True

# --- 统计文件加载 ---
def load_all_precomputed_rules(input_dir):
    """
    加载预处理生成的所有 .json 文件。
    """
    print(f"--- 正在从 {input_dir} 加载所有统计信息则... ---")
    rules = {}

    files_to_load = [
        "author_activity_weights.json",
        "author_primary_fields.json",
        "author_coauthor_graph.json",
        "authors_per_paper_dist.json",
        "topic_hotness.json",
        "topic_hierarchy_existing.json",
        "topic_hierarchy_new.json",
        "citation_count_dist.json",
        "topic_to_papers_pool.json",
        "subfield_to_papers_pool.json",
        "work_type_dist.json",
        "work_language_dist.json",
        "topic_text_map.json",
        "topic_text_map.json",
        "topic_subfield_map.json",
        "topic_field_map.json",
        "field_hierarchy_existing.json",
        "topic_vectors.json"
    ]

    for filename in files_to_load:
        key_name = filename.split('.')[0]
        file_path = os.path.join(input_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                rules[key_name] = json.load(f)
            print(f"    (加载成功) {filename}")
        except FileNotFoundError:
            print(f"    ERROR: 未找到规则文件: {filename}。将使用空 {{}}。")
            rules[key_name] = {}
        except Exception as e:
            print(f"    ERROR: 加载 {filename} 失败: {e}")
            rules[key_name] = {}

    print("--- 统计信息加载完毕。 ---")
    return rules
def _run_periodic_recompute(output_path, project_root, input_dir, all_topics_path):
    """
    调用 precompute_statistics.py 脚本，
    读取 output_path 中的数据，并重写 input_dir (collect_output) 中的统计信息。
    """

    # 定义 precompute_statistics.py 脚本的路径
    precompute_script_path = os.path.join(os.path.dirname(__file__), "precompute_statistics.py")

    # 定义要读取的路径 (output 目录)
    recompute_csv_dir = os.path.join(output_path, "csv-files")
    recompute_edges_dir = os.path.join(output_path, "graph_edges")

    # 定义要写入的路径 (collect_output 目录)
    collect_output_dir = input_dir

    # 清理旧的统计文件
    print(" 正在删除旧的统计文件...")
    try:
        for f in os.listdir(collect_output_dir):
            if f.endswith(".json"):
                os.remove(os.path.join(collect_output_dir, f))
    except Exception as e:
        print(f" WARNING：清理 {collect_output_dir} 失败: {e}")

    # 构建 Python 命令
    python_cmd = [
        sys.executable,
        precompute_script_path,
        recompute_csv_dir,
        recompute_edges_dir,
        all_topics_path,
        collect_output_dir
    ]

    print(" 正在执行预处理脚本:")
    print(f" {' '.join(python_cmd)}")

    # 执行脚本
    try:
        subprocess.run(python_cmd, check=True)
        print(" 预处理脚本执行成功。")
    except subprocess.CalledProcessError as e:
        print("ERROR：周期性预处理失败! !!!")
        print(e)
    except FileNotFoundError:
        print("ERROR：找不到 precompute_statistics.py 脚本! !!!")

RULES = None
auth_sel = None
top_sel = None
cit_sel = None
work_samplers = None
PROCESS_NUM = int(os.environ.get("MAP_BENCH_PROCESS_NUM", "32"))
TASK_BATCH_SIZE = max(1, int(os.environ.get("MAP_BENCH_TASK_BATCH_SIZE", "1")))
PRELOAD_KENLM_TOP_N = max(0, int(os.environ.get("MAP_BENCH_PRELOAD_KENLM_TOP_N", "0")))
P2_STATS_ENABLED = os.environ.get("MAP_BENCH_CACHE_STATS", "0") == "1"

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
except NameError:
    SCRIPT_DIR = os.getcwd()
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SOURCE_DATA_ROOT = os.environ.get(
    "MAP_BENCH_SOURCE_DATA_ROOT",
    os.path.join(PROJECT_ROOT, "map-s"),
)
INPUT_DIR = os.environ.get(
    "MAP_BENCH_COLLECT_OUTPUT_DIR",
    os.path.join(PROJECT_ROOT, "collect_output"),
)
PATH_TOPICS_ALL = os.path.join(
    SOURCE_DATA_ROOT, "csv-files", "topics_all.csv"
)
MODEL_PATH = os.environ.get(
    "MAP_BENCH_EMBED_MODEL_PATH",
    os.path.join(PROJECT_ROOT, "all-MiniLM-L6-v2"),
)
# --- 全局加载 RULES 和选择器 ---
print("--- [主进程] 正在加载全局规则和选择器... ---")

RULES = load_all_precomputed_rules(INPUT_DIR)

auth_sel = author_selector.AuthorSelector(
    RULES["author_activity_weights"],
    RULES["author_primary_fields"],
    RULES["authors_per_paper_dist"],
    RULES["author_coauthor_graph"]
)
top_sel = topic_selector.TopicSelector(
    RULES["topic_hotness"],
    RULES["topic_hierarchy_existing"],
    RULES["topic_hierarchy_new"],
    RULES["field_hierarchy_existing"],
    RULES["topic_field_map"],
    PATH_TOPICS_ALL
)
cit_sel = citation_selector.CitationSelector(
    RULES["citation_count_dist"],
    RULES["topic_to_papers_pool"],
    RULES["subfield_to_papers_pool"],
    PATH_TOPICS_ALL
)
# work_samplers = work_generator.Samplers(
#     RULES.get("work_type_dist"),
#     RULES.get("work_language_dist")
# )
print("--- [主进程] 全局加载完毕。 ---")
def init_worker():
    """初始化工作进程的全局变量"""
    global work_generator, work_samplers # 确保引用局部导入的 work_generator
    import work_generator
    unique_seed_base = int(time.time() * 1000) + os.getpid()

    seed_32bit = unique_seed_base % (2**32 - 1)

    random.seed(unique_seed_base)
    np.random.seed(seed_32bit)
    work_generator.initialize_embedding_model(MODEL_PATH)
    # topic_vec_path = os.path.join(SOURCE_DATA_ROOT, "vector", "topics_vec.csv")
    # work_generator.initialize_topic_cache(topic_vec_path)
    work_samplers = work_generator.Samplers(
        RULES.get("work_type_dist"),
        RULES.get("work_language_dist")
    )

def worker_task(task_args):
    """
    生产者函数，执行所有CPU密集型工作。
    """
    global work_generator
    current_year, p_author, p_topic = task_args

    try:
        # 作者选择
        author_team, core_team_ids, new_author_package = auth_sel.get_author_team(
            p_new_author=p_author,
            current_year=current_year
        )

        # 主题选择
        selected_topics_list, is_new_topic = top_sel.get_topics(
            author_team=author_team,
            p_new_topic=p_topic
        )
        primary_topic = selected_topics_list[0]

        # 引文选择
        citations_list = cit_sel.get_citations(
            selected_topic_metadata=primary_topic
        )

        # 生成文章包
        work_package = work_generator.generate_work_package(
            new_work_id=None, # (使用 None 占位符)
            current_year=current_year,
            author_team=author_team,
            core_team_ids=core_team_ids,
            selected_topics_list=selected_topics_list,
            citations_list=citations_list,
            samplers=work_samplers,
            topic_text_map = RULES.get("topic_text_map", {}),
            topic_subfield_map=RULES.get("topic_subfield_map", {}),
            topic_vectors_map=RULES.get("topic_vectors", {}),
            use_complex_text_gen=USE_COMPLEX_TEXT
        )

        # 返回所有需要写入的数据
        result = {
            "status": "success",
            "work_package": work_package,
            "new_author_package": new_author_package,
            "selected_topics_list": selected_topics_list,
            "is_new_topic": is_new_topic
        }
        if P2_STATS_ENABLED:
            result["worker_pid"] = os.getpid()
            if hasattr(work_generator, "get_text_cache_stats"):
                result["text_cache_stats"] = work_generator.get_text_cache_stats()
            if hasattr(work_generator, "get_text_score_cache_stats"):
                result["text_score_cache_stats"] = work_generator.get_text_score_cache_stats()
        return result
    except Exception as e:
        print(f" ERROR in worker process (PID: {os.getpid()}): {e}")
        return {"status": "error", "error": str(e)}

def worker_batch_task(task_args):
    """生成一批文章，减少 multiprocessing task 调度开销。"""
    current_year, p_author, p_topic, batch_size = task_args
    return [worker_task((current_year, p_author, p_topic)) for _ in range(batch_size)]

def _iter_worker_results(pool, year, p_author, p_topic, n_articles):
    """按配置选择单篇或批量 task，并保持向主循环逐篇 yield 结果。"""
    if TASK_BATCH_SIZE <= 1:
        tasks = [(year, p_author, p_topic)] * n_articles
        yield from pool.imap_unordered(worker_task, tasks)
        return

    batch_tasks = []
    remaining = n_articles
    while remaining > 0:
        size = min(TASK_BATCH_SIZE, remaining)
        batch_tasks.append((year, p_author, p_topic, size))
        remaining -= size

    for batch_result in pool.imap_unordered(worker_batch_task, batch_tasks):
        for result in batch_result:
            yield result

def _preload_hot_kenlm_models(top_n):
    """父进程预加载高热度 KenLM 模型，fork 后共享只读页。"""
    if top_n <= 0:
        return
    try:
        import work_generator
    except Exception as e:
        print(f"WARNING: 无法导入 work_generator 进行 KenLM 预加载: {e}")
        return

    topic_hotness = RULES.get("topic_hotness", {})
    topic_subfield_map = RULES.get("topic_subfield_map", {})
    if not topic_hotness:
        print("WARNING: topic_hotness 为空，跳过 KenLM 预加载。")
        return

    sorted_topics = sorted(topic_hotness.items(), key=lambda item: item[1], reverse=True)[:top_n]
    loaded = 0
    print(f"--- [主进程] 预加载 Top {len(sorted_topics)} KenLM 模型... ---")
    for topic_id, _ in tqdm(sorted_topics, desc="预加载 KenLM", leave=False):
        topic_id_str = str(topic_id)
        subfield_id = topic_subfield_map.get(topic_id_str)
        if work_generator._load_model(topic_id_str, subfield_id):
            loaded += 1
    print(f"--- [主进程] KenLM 预加载完成: {loaded}/{len(sorted_topics)} ---")

# --- 主生成器 ---
if __name__ == "__main__":

    if len(sys.argv) != 6:
        print("错误：需要 5 个参数: <ScaleFactor> <Mode> <OutputPath> <TmpPath> <TEXT_GEN_MODE>")
        sys.exit(1)

    SF_INPUT = float(sys.argv[1])
    MODE_INPUT = int(sys.argv[2])
    OUTPUT_PATH_ARG = sys.argv[3]
    TMP_PATH_ARG = sys.argv[4]
    TEXT_MODE_INPUT = int(sys.argv[5])
    USE_COMPLEX_TEXT = (TEXT_MODE_INPUT == 1)
    import work_generator
    # try:
    #     SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    #     PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    # except NameError:
    #     SCRIPT_DIR = os.getcwd()
    #     PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    # INPUT_DIR = os.path.join(PROJECT_ROOT, "collect_output")
    # PATH_TOPICS_ALL = os.path.join(
    #     PROJECT_ROOT, "openalex_small", "csv-files", "topics_all.csv"
    # )

    # RULES = load_all_precomputed_rules(INPUT_DIR)


    sf1_stats_path = os.path.join(INPUT_DIR, "sf1_stats.json")
    max_author_id = 0
    max_work_id = 0
    try:
        with open(sf1_stats_path, 'r') as f:
            sf1_stats = json.load(f)
            max_author_id = sf1_stats.get("max_author_id", 0)
            max_work_id = sf1_stats.get("max_work_id", 0)
    except FileNotFoundError:
        print(f"WARNING: 找不到 {sf1_stats_path}。ID 计数器将从默认值开始。")


    author_generate.initialize_id_counter(max_author_id)
    work_generator.initialize_work_id_counter(max_work_id)


    plan = incremental_calculator.calculate_increments(SF_INPUT, MODE_INPUT, debug_print=False)

    # 执行主循环
    print("--- 开始执行数据生成... ---")
    print(f"--- 文本生成模式: {'[KenLM]' if USE_COMPLEX_TEXT else '[Faker]'} ---")
    print(f"--- 并行配置: processes={PROCESS_NUM}, batch_size={TASK_BATCH_SIZE}, preload_kenlm_top_n={PRELOAD_KENLM_TOP_N} ---")
    if USE_COMPLEX_TEXT and PRELOAD_KENLM_TOP_N > 0:
        _preload_hot_kenlm_models(PRELOAD_KENLM_TOP_N)
    if not plan["time_series"]:
        print("--- 计划为空 (可能 SF=1)，无需生成。---")
    else:
        year_counter = 0

        # io_topic_selector = topic_selector.TopicSelector(
        #      RULES["topic_hotness"],
        #      RULES["topic_hierarchy_existing"],
        #      RULES["topic_hierarchy_new"],
        #      PATH_TOPICS_ALL
        # )

        # n_cpus = multiprocessing.cpu_count()
        # pool_size = max(1, n_cpus - 60) # 留一个核心给消费者(主进程)
        pool_size = PROCESS_NUM
        topics_written_in_this_cycle = set()
        print(f"--- 正在启动 {pool_size} 个工作进程... ---")

        pool = multiprocessing.Pool(
            processes=pool_size,
            initializer=init_worker, # (调用初始化函数)
            initargs=() # (传递参数)
        )

        for year in tqdm(plan["time_series"], desc="年度进度"):
            year_counter += 1
            print(f"\n--- 正在为 {year} 年准备临时写入文件(-> {TMP_PATH_ARG})... ---")

            writer = data_writer.DataWriter(TMP_PATH_ARG)

            n_articles = plan["article_increment"][year]
            p_author = plan["author_prob_per_article"][year]
            p_topic = plan["topic_prob_per_article"][year]

            # topics_written_this_year = set()


            print(f"--- {year} 年: 正在提交 {n_articles} 篇文章任务... ---")

            result_iter = _iter_worker_results(pool, year, p_author, p_topic, n_articles)
            text_cache_stats_by_worker = {}
            text_score_cache_stats_by_worker = {}
            processed_articles = 0
            for result in tqdm(result_iter, total=n_articles, desc=f"生成 {year} 年的文章", leave=False):

                if result["status"] == "error":
                    print(f" WARNING: 一个工作任务失败: {result['error']}")
                    continue
                processed_articles += 1
                if P2_STATS_ENABLED:
                    if result.get("text_cache_stats"):
                        text_cache_stats_by_worker[result.get("worker_pid")] = result["text_cache_stats"]
                    if result.get("text_score_cache_stats"):
                        text_score_cache_stats_by_worker[result.get("worker_pid")] = result["text_score_cache_stats"]
                    if processed_articles % 100 == 0:
                        if text_cache_stats_by_worker:
                            totals = {"lookups": 0, "hits": 0, "misses": 0, "stores": 0}
                            for stats in text_cache_stats_by_worker.values():
                                for key in totals:
                                    totals[key] += stats.get(key, 0)
                            hit_rate = totals["hits"] / totals["lookups"] if totals["lookups"] else 0
                            print(
                                f"--- P2 cache stats: lookups={totals['lookups']}, hits={totals['hits']}, "
                                f"hit_rate={hit_rate:.2%}, stores={totals['stores']} ---",
                                flush=True
                            )
                        if text_score_cache_stats_by_worker:
                            score_totals = {"lookups": 0, "hits": 0, "misses": 0, "builds": 0, "cached_models": 0}
                            for stats in text_score_cache_stats_by_worker.values():
                                for key in score_totals:
                                    score_totals[key] += stats.get(key, 0)
                            score_hit_rate = score_totals["hits"] / score_totals["lookups"] if score_totals["lookups"] else 0
                            print(
                                f"--- P4 score cache stats: lookups={score_totals['lookups']}, hits={score_totals['hits']}, "
                                f"hit_rate={score_hit_rate:.2%}, builds={score_totals['builds']}, "
                                f"cached_models={score_totals['cached_models']} ---",
                                flush=True
                            )

                # --- 消费者开始工作 (状态管理 和 I/O) ---

                work_package = result["work_package"]
                new_author_package = result["new_author_package"]

                # if new_author_package:
                #     real_author_id = author_generate._get_new_author_id()

                #     new_author_package["id"] = real_author_id
                #     pkg_data = new_author_package["__full_data__"]
                #     pkg_data["relation"]["id"] = real_author_id
                #     pkg_data["relation"]["works_api_url"] = f"https://api.openalex.org/works?filter=author.id:A{real_author_id}"
                #     pkg_data["doc"]["id"] = real_author_id
                #     pkg_data["vertex"]["id"] = real_author_id

                #     for auth in work_package["work_doc"]["doc"]["authorships"]:
                #         if auth["author"]["id"] is None:
                #             auth["author"]["id"] = real_author_id
                #     for edge in work_package["work_author_edges"]:
                #         if edge["endid"] is None:
                #             edge["endid"] = real_author_id

                #     writer.write_new_author(pkg_data)
                if new_author_package:
                    temp_to_real_id = {} # 建立“假ID -> 真ID”

                    # 1. 循环处理每一个新作者，分配真实 ID
                    for new_auth_item in new_author_package:
                        temp_id = new_auth_item.get("id")
                        real_author_id = author_generate._get_new_author_id()
                        temp_to_real_id[temp_id] = real_author_id

                        new_auth_item["id"] = real_author_id
                        pkg_data = new_auth_item["__full_data__"]
                        pkg_data["relation"]["id"] = real_author_id
                        pkg_data["relation"]["works_api_url"] = f"https://api.openalex.org/works?filter=author.id:A{real_author_id}"
                        pkg_data["doc"]["id"] = real_author_id
                        pkg_data["vertex"]["id"] = real_author_id

                        writer.write_new_author(pkg_data)

                    for auth in work_package["work_doc"]["doc"]["authorships"]:
                        auth_id = auth["author"]["id"]
                        if auth_id in temp_to_real_id:
                            auth["author"]["id"] = temp_to_real_id[auth_id]

                    for edge in work_package["work_author_edges"]:
                        edge_id = edge["endid"]
                        if edge_id in temp_to_real_id:
                            edge["endid"] = temp_to_real_id[edge_id]
                    for edge in work_package["author_author_edges"]:
                        if edge["startid"] in temp_to_real_id:
                            edge["startid"] = temp_to_real_id[edge["startid"]]
                        if edge["endid"] in temp_to_real_id:
                            edge["endid"] = temp_to_real_id[edge["endid"]]

                        # 因为现在都变成了真实的整数 ID，我们需要重新做一次大小排序，确保 startid 永远小于 endid
                        real_start = min(edge["startid"], edge["endid"])
                        real_end = max(edge["startid"], edge["endid"])
                        edge["startid"] = real_start
                        edge["endid"] = real_end

                if result["is_new_topic"]:
                    for i, topic_data in enumerate(result["selected_topics_list"]):
                        topic_id = topic_data["id"]
                        topic_id_str = str(topic_id)

                        if topic_id_str not in topics_written_in_this_cycle:
                            topic_row = top_sel.get_topic_row_for_writing(topic_id_str)
                            if topic_row:
                                writer.write_new_topic(topic_row)

                                if i == 0:
                                    topic_vec_str = work_package.get("topic_vector_str")
                                    if topic_vec_str:
                                        writer.write_topic_vector(topic_id, topic_vec_str)

                                topics_written_in_this_cycle.add(topic_id_str)

                real_work_id = work_generator.get_new_work_id()

                work_package["work_relation"]["id"] = real_work_id
                work_package["work_relation"]["cited_by_api_url"] = f"https://api.openalex.org/works?filter=cites:W{real_work_id}"
                work_package["work_doc"]["id"] = real_work_id
                work_package["work_vertex"]["id"] = real_work_id

                if "work_vector" in work_package:
                    work_package["work_vector"]["id"] = real_work_id
                    writer.write_work_vector(work_package["work_vector"])
                for edge in work_package["work_author_edges"]:
                    edge["startid"] = real_work_id
                # work_package["work_topic_edge"]["startid"] = real_work_id
                topic_edges = work_package.get("work_topic_edges")
                if topic_edges and isinstance(topic_edges, list):
                    for edge in topic_edges:
                        edge["startid"] = real_work_id
                elif "work_topic_edge" in work_package:
                    # 如果还是旧的单数字典 (做个兼容)
                    edge_data = work_package["work_topic_edge"]
                    if isinstance(edge_data, list): # 如果键名是单数但内容是列表
                         for edge in edge_data:
                            edge["startid"] = real_work_id
                    else:
                         edge_data["startid"] = real_work_id
                for edge in work_package["work_ref_edges"]:
                    edge["startid"] = real_work_id
                for edge in work_package.get("author_author_edges", []):
                    props = edge.get("properties", {})
                    for item in props.get("list", []):
                        if item.get("work_id") is None:
                            item["work_id"] = real_work_id


                # if new_author_package:
                #     # 提取这篇论文最终定型的所有真实作者 ID
                #     all_author_ids = [auth["author"]["id"] for auth in work_package["work_doc"]["doc"]["authorships"] if auth["author"]["id"] is not None]

                #     # 提取本轮刚生成的几个新作者 ID 存进集合，方便快速判断
                #     new_author_ids = {item["id"] for item in new_author_package}

                #     # 双重循环：遍历团队中所有的两两组合
                #     for i in range(len(all_author_ids)):
                #         for j in range(i + 1, len(all_author_ids)):
                #             id1 = all_author_ids[i]
                #             id2 = all_author_ids[j]

                #             # 只要这对组合里包含哪怕一个新作者，就建边
                #             if id1 in new_author_ids or id2 in new_author_ids:
                #                 start_id = min(id1, id2)
                #                 end_id = max(id1, id2)
                #                 work_package["author_author_edges"].append({
                #                     "startid": start_id, "endid": end_id,
                #                     "properties": {"cnt": 1, "list": [{"year": year, "work_id": real_work_id}]}
                #                 })

                writer.write_new_work_package(work_package)

            writer.close_all_files()

            try:
                annual_updater.run_annual_update(OUTPUT_PATH_ARG,TMP_PATH_ARG)
                annual_updater.clear_tmp_files(TMP_PATH_ARG)
                print(f"--- 【年度更新 {year}】: 成功。---")
            except Exception as e:
                print(f"ERROR：年度更新 {year} 失败: {e} !!!")

            if year_counter % 5 == 0 and year != plan["time_series"][-1]:
                print(f"\n--- 正在关闭进程池以重新计算统计数据... ---")
                pool.close()
                pool.join()

                _run_periodic_recompute(OUTPUT_PATH_ARG, PROJECT_ROOT, INPUT_DIR, PATH_TOPICS_ALL)

                print("--- 正在重新加载新规则... ---")
                RULES = load_all_precomputed_rules(INPUT_DIR)
                auth_sel = author_selector.AuthorSelector(
                    RULES["author_activity_weights"],
                    RULES["author_primary_fields"],
                    RULES["authors_per_paper_dist"],
                    RULES["author_coauthor_graph"]
                )
                top_sel = topic_selector.TopicSelector(
                    RULES["topic_hotness"],
                    RULES["topic_hierarchy_existing"],
                    RULES["topic_hierarchy_new"],
                    RULES["field_hierarchy_existing"],  # 补上这个
                    RULES["topic_field_map"],           # 补上这个
                    PATH_TOPICS_ALL                     # 补上这个
                )
                cit_sel = citation_selector.CitationSelector(
                    RULES["citation_count_dist"],
                    RULES["topic_to_papers_pool"],
                    RULES["subfield_to_papers_pool"],
                    PATH_TOPICS_ALL
                )
                # work_samplers = work_generator.Samplers(
                #     RULES.get("work_type_dist"),
                #     RULES.get("work_language_dist")
                # )
                topics_written_in_this_cycle = set()
                print(f"--- 正在重启 {pool_size} 个工作进程... ---")
                pool = multiprocessing.Pool(
                    processes=pool_size,
                    initializer=init_worker,
                    initargs=()
                )

        pool.close()
        pool.join()

    print("--- 运行完毕。---")
