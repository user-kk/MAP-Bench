import random
import datetime
from faker import Faker
import uuid

fake = Faker()
_CURRENT_MAX_AUTHOR_ID = 0

def initialize_id_counter(max_id_from_sf1):
    """
    初始化设置 ID 计数器的起始点。
    """
    global _CURRENT_MAX_AUTHOR_ID
    if max_id_from_sf1 and max_id_from_sf1 > 0:
        _CURRENT_MAX_AUTHOR_ID = max_id_from_sf1
    else:
        _CURRENT_MAX_AUTHOR_ID = 5500000000
    # print(f"--- 作者ID已初始化，起始id: {_CURRENT_MAX_AUTHOR_ID} ---")

def _get_new_author_id():
    """
    作者ID递增生成。
    """
    global _CURRENT_MAX_AUTHOR_ID
    _CURRENT_MAX_AUTHOR_ID += 1
    return _CURRENT_MAX_AUTHOR_ID

def _generate_random_name():
    return fake.name()


# --- 主函数 ---

def get_new_author(seed_field, seed_subfield, core_author_institution_id, current_year):
    """
    Args:
        seed_field (str): 核心作者的领域 (来自 author_selector)
        seed_subfield (str): 核心作者的子领域 (来自 author_selector)
        core_author_institution_id (int): 核心作者的机构ID (来自 author_selector)
        current_year (int): 模拟的当前年份 (来自 main_generator)

    Returns:
        dict: 一个包含新作者所有 *模型数据* 的字典。
    """

    # --- 生成属性  ---
    new_id = f"temp_{uuid.uuid4().hex[:8]}"
    # new_id = _get_new_author_id()
    new_name = _generate_random_name()

    # 新作者跟随核心作者的机构
    new_institution_id = core_author_institution_id
    new_last_known_institution = None


    try:
        # 1. 创建该年份的1月1日
        start_of_year = datetime.date(current_year, 1, 1)
        # 2. 随机偏移 0 到 364 天
        random_day_offset = random.randint(0, 364)
        # 3. 计算随机日期
        random_date = start_of_year + datetime.timedelta(days=random_day_offset)
        random_date_str = random_date.strftime("%Y-%m-%d")
    except ValueError:
        # 处理闰年等边缘情况
        random_date_str = f"{current_year}-01-01"

    current_time_str = datetime.datetime.now().strftime("%H:%M:%S")
    update_timestamp = f"{random_date_str} {current_time_str}"
    # 日期等于t_i (年份) + 当前时间
    # 格式为 "YYYY-MM-DDTHH:MM:SS" (假设设在模拟年份的1月1日生成)

    # --- 构建authors.csv  ---
    author_relation = {
        "id": new_id,
        "display_name": new_name,
        "works_count": 1,
        "cited_by_count": 0,
        "last_known_institution": new_last_known_institution, # 跟随核心作者
        "works_api_url": f"https://api.openalex.org/works?filter=author.id:A{new_id}",
        "updated_date": update_timestamp,
        "institution_id": new_institution_id
    }

    # --- 构建authors_doc.csv ---
    author_doc = {
        "id": new_id,
        "doc": {
            "orcid": None,
            "display_name_alternatives": [new_name]
        }
    }

    # --- 构建authors_v.csv ---
    author_vertex = {
        "id": new_id,
        "properties": {
            "display_name": new_name,
            "works_count": 1,
            "cited_by_count": 0
        }
    }

    # --- 构建 author_selector需要的返回格式 ---
    author_selector_return_data = {
        "id": new_id,
        "display_name": new_name,
        "primary_field": seed_field,
        "primary_subfield": seed_subfield,
        "institution_id":  new_institution_id,


        "__full_data__": {
            "relation": author_relation,
            "doc": author_doc,
            "vertex": author_vertex
        }
    }

    # if writer_instance:
    #     try:
    #         writer_instance.write_new_author(author_selector_return_data["__full_data__"])
    #         # print(f" (写入成功) 已将新作者 {new_id} 写入文件。")
    #     except Exception as e:
    #         print(f" ERROR: 写入作者 {new_id} 失败: {e}")
    # else:
    #     print(f" WARNING: 未传入 writer 实例，跳过写入。")

    return author_selector_return_data
