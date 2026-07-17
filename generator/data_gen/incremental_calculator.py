import numpy as np
import os
import json
import sys

# --- 配置  ---
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
except NameError:
    SCRIPT_DIR = os.getcwd()
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

INPUT_DIR = os.environ.get("MAP_BENCH_COLLECT_OUTPUT_DIR", os.path.join(PROJECT_ROOT, "collect_output"))
SF1_STATS_FILE = os.path.join(INPUT_DIR, "sf1_stats.json")
ARTIFICIAL_NOISE_RATIO = 0.15
# 模式一 (时间扩展) 的概率配置
P_NEW_AUTHOR_FIXED = 0.2  # 固定的新作者生成概率
P_NEW_TOPIC_INITIAL = 0.05 # 新主题的初始概率
P_NEW_TOPIC_FINAL = 0.0    # 新主题的最终概率 (线性递减到0)

# --- 加载统计数据 ---
# (脚本被导入时只执行一次)

def load_sf1_stats():
    """加载 SF1 统计数据。"""

    print("--- 正在加载 SF=1 预计算统计... ---")
    try:
        with open(SF1_STATS_FILE, 'r', encoding='utf-8', buffering=8*1024*1024) as f:
            stats = json.load(f)

            stats['article_distribution'] = {
                int(k): v for k, v in stats['article_distribution'].items()
            }

            # print(f"    {SF1_STATS_FILE} 加载成功。")
            return stats
    except FileNotFoundError:
        print(f" ERROR：找不到 {SF1_STATS_FILE}。")
        print(f" 请先在根目录下运行main.sh以生成所需的统计数据。")
        return None
    except Exception as e:
        print(f"!!! [增量计算器] 致命错误：加载 {SF1_STATS_FILE} 时出错: {e}")
        return None

# 在模块加载时就执行此操作
SF1_STATS = load_sf1_stats()
if SF1_STATS is None:
    print("无法加载 SF=1 统计数据，程序将退出。")
    sys.exit(1)


# def _extrapolate_growth(sf1_stats, total_new_articles):
#     """
#     模式一时间扩展的增量计算
#     """
#     # 拟合数据 (x=年份, y=产量)
#     years_sf1 = np.array(sf1_stats["time_range"])
#     counts_sf1 = np.array([sf1_stats["article_distribution"][y] for y in years_sf1])

#     # 移除最后一年数据
#     if len(years_sf1) > 1:
#         # print(f" 计算时将忽略最后一年 ({years_sf1[-1]}) 的数据，")
#         # print(f" 因为它被视为不完整 (产量: {counts_sf1[-1]})。")
#         valid_counts = counts_sf1[:-1] # 只保留 2022, 2023, 2024 的产量
#     else:
#         valid_counts = counts_for_fit
#     RECENT_WINDOW = 5
#     counts_for_fit = valid_counts[-RECENT_WINDOW:]
#     # 计算均值和标准差
#     if len(counts_for_fit) == 0:
#         print("ERROR: 没有任何有效历史数据。")
#         return [], {}
#     #均值+噪声
#     mean_count = np.mean(counts_for_fit)
#     std_dev_count = mean_count * ARTIFICIAL_NOISE_RATIO

#     # print(f" 均值计算完成。")
#     # print(f" 未来的文章产量将从 N(mean={mean_count:.2f}, std={std_dev_count:.2f} (人工)) 正态分布中采样。")

#     new_time_series = []
#     annual_article_increment = {}

#     last_year_sf1 = sf1_stats["time_range"][-1]
#     current_year = last_year_sf1 + 1
#     articles_generated = 0

#     while articles_generated < total_new_articles:

#         predicted_count = np.random.normal(mean_count, std_dev_count)

#         articles_to_generate_this_year = int(max(1, predicted_count))

#         remaining_articles = total_new_articles - articles_generated
#         if articles_to_generate_this_year > remaining_articles:
#             articles_to_generate_this_year = int(remaining_articles)

#         new_time_series.append(current_year)
#         annual_article_increment[current_year] = articles_to_generate_this_year

#         articles_generated += articles_to_generate_this_year
#         current_year += 1

#     return new_time_series, annual_article_increment

def _extrapolate_growth(sf1_stats, total_new_articles):
    """
    模式一：带随机波动的自然增长策略

    逻辑：
    1. 总量控制：严格受限于 total_new_articles (由 SF 决定)。
    2. 趋势：基于 2024 或历史峰值，设定微小的自然增长率 (如 2%)。
    3. 波动：每年增加随机抖动，避免曲线死板。
    4. 2025 修复：优先用配额填补 2025 年的数据缺口。
    """

    # --- 策略配置 ---
    ANNUAL_GROWTH_RATE = 0.01  # 每年自然增长 1%
    VOLATILITY = 0.05          # 波动率 ±5%
    # ----------------

    # 1. 确定基准线
    years_all = sorted([int(y) for y in sf1_stats["article_distribution"].keys()])
    valid_counts = [sf1_stats["article_distribution"][y] for y in years_all if y < 2025]

    if not valid_counts:
        baseline_count = 100
        last_valid_year = 2024
    else:
        # 取历史最大值作为能力的基准，防止被某一年小年拉低
        baseline_count = valid_counts[-1]
        last_valid_year = max([y for y in years_all if y < 2025])

    # print(f" 基准值: {baseline_count} (基于 {last_valid_year} 及以前)")

    new_time_series = []
    annual_article_increment = {}
    articles_generated_so_far = 0

    # 定义单年预测函数
    def predict_for_year(target_year):
        year_diff = target_year - last_valid_year
        # 理论值 = 基准 * (1.02 ^ 年差)
        theoretical_val = baseline_count * ((1 + ANNUAL_GROWTH_RATE) ** year_diff)
        # 加入噪声 = 理论值 * (0.95 ~ 1.05)
        noise = np.random.uniform(1 - VOLATILITY, 1 + VOLATILITY)
        final_val = int(theoretical_val * noise)
        return max(1, final_val)

    # ==================================================
    # 阶段 A: 2025 年补坑 (优先使用配额)
    # ==================================================
    actual_2025 = sf1_stats["article_distribution"].get(2025, 0)
    target_2025 = predict_for_year(2025)

    # 如果 2025 实际值 < 目标值，且我们还有配额
    if actual_2025 < target_2025:
        gap = target_2025 - actual_2025
        # 能补多少补多少，不能超过总配额
        amount_to_add = min(gap, total_new_articles - articles_generated_so_far)

        if amount_to_add > 0:
            new_time_series.append(2025)
            annual_article_increment[2025] = int(amount_to_add)
            articles_generated_so_far += amount_to_add

    # ==================================================
    # 阶段 B: 2026+ 未来生成 (消耗剩余配额)
    # ==================================================
    current_year = 2026

    # 只要配额还没用完，就往后一年一年算
    while articles_generated_so_far < total_new_articles:
        # 1. 算出这一年“应该”有多少篇
        predicted_count = predict_for_year(current_year)

        # 2. 看看钱包(剩余配额)还够不够
        remaining = total_new_articles - articles_generated_so_far

        # 3. 取小值：如果预测要 1500，但只剩 500 了，那就只生 500，然后结束
        count_this_year = int(min(predicted_count, remaining))

        if count_this_year > 0:
            new_time_series.append(current_year)
            annual_article_increment[current_year] = count_this_year
            articles_generated_so_far += count_this_year
        else:
            break # 配额耗尽，停止

        current_year += 1

    return new_time_series, annual_article_increment

def _calculate_topic_probability(current_year, start_year, end_year):
    """
    计算“随时间递减”的主题概率。
    """
    if start_year == end_year:
        return P_NEW_TOPIC_INITIAL

    total_duration = end_year - start_year

    elapsed_ratio = (current_year - start_year) / total_duration

    prob = P_NEW_TOPIC_INITIAL - (P_NEW_TOPIC_INITIAL - P_NEW_TOPIC_FINAL) * elapsed_ratio
    return max(P_NEW_TOPIC_FINAL, prob)

def _pretty_print_plan(plan):
    """
    打印执行计划
    """
    print("\n------ 增量计算器执行计划 ------")
    print(f"    模拟模式: {plan['mode']}")
    print(f"    目标 SF: {plan['sf']}")
    print(f"    总计新增文章: {plan['total_new_articles']}")
    time_series = plan['time_series']

    if plan['mode'] == 1:
        print(f"    模拟时间范围: {time_series[0]} to {time_series[-1]} (共 {len(time_series)} 年)")
        print(f"    新作者生成概率 (固定): {P_NEW_AUTHOR_FIXED * 100:.1f}%")
        print("\n    年度计划 (抽样展示):")
        for i, year in enumerate(time_series):
            if i < 3 or i >= len(time_series) - 3:
                print(f"    - {year}: "
                      f"文章 = {plan['article_increment'][year]} (来自均值+噪声), "
                      f"作者 P = {plan['author_prob_per_article'][year]*100:.1f}%, "
                      f"主题 P = {plan['topic_prob_per_article'][year]*100:.2f}%")
            elif i == 3:
                print("      ...")

    elif plan['mode'] == 2:
        print(f"    模拟时间范围: {time_series[0]} to {time_series[-1]} (固定)")
        print("\n    年度计划 (抽样展示):")
        for i, year in enumerate(time_series):
            if i < 3 or i >= len(time_series) - 3:
                print(f"    - {year}: "
                      f"新增文章 = {plan['article_increment'][year]}")
            elif i == 3:
                print("      ...")
    print("------ 执行计划结束 ------\n")

# --- 主函数  ---

def calculate_increments(sf, mode, debug_print=True):
    """
    增量计算器主函数

    Args:
        sf (float): 目标 SF。
        mode (int): 1 (时间扩展) 或 2 (密度扩展)。
        debug_print (bool): 是否打印执行计划。

    Returns:
        dict
    """

    total_articles_sf1 = SF1_STATS["total_articles"]
    time_range_sf1 = SF1_STATS["time_range"]
    article_dist_sf1 = SF1_STATS["article_distribution"]

    if mode == 2:
        # --- 模式二：密度扩展 ---
        total_new_articles = int((sf - 1) * total_articles_sf1)
        annual_article_increment = {}
        if total_articles_sf1 > 0:
            # 按比例分配
            for year in time_range_sf1:
                year_share = article_dist_sf1.get(year, 0) / total_articles_sf1
                annual_article_increment[year] = int(total_new_articles * year_share)

        # 处理零头
        current_sum = sum(annual_article_increment.values())
        diff = int(total_new_articles) - current_sum
        if diff != 0 and time_range_sf1:
             annual_article_increment[time_range_sf1[-1]] += diff

        plan = {
            "mode": 2, "sf": sf, "total_new_articles": total_new_articles,
            "time_series": time_range_sf1,
            "article_increment": annual_article_increment,
            "author_prob_per_article": {year: 0.0 for year in time_range_sf1},
            "topic_prob_per_article": {year: 0.0 for year in time_range_sf1}
        }

    elif mode == 1:
        # --- 模式一：时间扩展 ---
        total_new_articles = int((sf - 1) * total_articles_sf1)

        new_time_series, annual_article_increment = _extrapolate_growth(
            SF1_STATS,
            total_new_articles
        )

        author_prob_map = {}
        topic_prob_map = {}

        if not new_time_series: # 处理 sf=1 (即 0 增量) 的情况
             plan = { "mode": 1, "sf": sf, "total_new_articles": 0, "time_series": [] }
        else:
            start_year = new_time_series[0]
            end_year = new_time_series[-1]

            for year in new_time_series:
                author_prob_map[year] = P_NEW_AUTHOR_FIXED
                topic_prob_map[year] = _calculate_topic_probability(year, start_year, end_year)

            plan = {
                "mode": 1, "sf": sf, "total_new_articles": total_new_articles,
                "time_series": new_time_series,
                "article_increment": annual_article_increment,
                "author_prob_per_article": author_prob_map,
                "topic_prob_per_article": topic_prob_map
            }

    else:
        raise ValueError("模式 (Mode) 必须是 1 (时间扩展) 或 2 (密度扩展)")

    if debug_print:
        _pretty_print_plan(plan)

    return plan

# ------ 测试 ------
if __name__ == "__main__":

    print(f"--- SF1 统计数据 (从 {SF1_STATS_FILE} 加载) ---")
    print(f"    总文章数: {SF1_STATS['total_articles']}")
    print(f"    总作者数: {SF1_STATS['total_authors']}")
    print(f"    总主题数: {SF1_STATS['total_topics']}")
    print(f"    时间范围: {SF1_STATS['time_range'][0]} to {SF1_STATS['time_range'][-1]}")
    print("---------------------------------")

    print("\n>>> 测试：主函数调用增量计算器 (模式一, SF=1.5) <<<")
    plan_mode1 = calculate_increments(sf=1.5, mode=1, debug_print=False)

    print("\n>>> 测试：主函数调用增量计算器 (模式二, SF=3) <<<")
    plan_mode2 = calculate_increments(sf=3, mode=2, debug_print=False)
