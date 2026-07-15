import pandas as pd
import csv
import os
import json
from tqdm import tqdm
from collections import defaultdict
import sys
import shutil
IO_BUF = 8 * 1024 * 1024
# --- 辅助：追加文件内容 ---
def _fast_append_csv(main_file_path, new_file_path):
    """
    直接以二进制流的方式将新文件的内容追加到主文件末尾。
    (修正版：解决了 'ab' 模式下无法读取导致的报错)
    """
    if not new_file_path or not os.path.exists(new_file_path):
        return

    # 1. 如果主文件不存在，直接移动
    if not os.path.exists(main_file_path):
        try:
            shutil.move(new_file_path, main_file_path)
        except Exception as e:
            # 跨设备移动失败则复制并删除
            shutil.copy(new_file_path, main_file_path)
            os.remove(new_file_path)
        return

    # 2. 追加逻辑
    try:
        # [步骤 A] 先以 'rb' (只读) 模式检查末尾是否有换行符
        needs_newline = False
        if os.path.getsize(main_file_path) > 0:
            with open(main_file_path, 'rb', buffering=IO_BUF) as f_check:
                f_check.seek(-1, 2)  # 移动到倒数第一个字节
                if f_check.read(1) != b'\n':
                    needs_newline = True

        # [步骤 B] 再以 'ab' (追加) 模式写入
        with open(main_file_path, 'ab', buffering=IO_BUF) as f_main:
            # 如果需要，补一个换行符
            if needs_newline:
                f_main.write(b'\n')

            # 追加新文件内容
            with open(new_file_path, 'rb', buffering=IO_BUF) as f_new:
                f_new.readline() # 跳过新文件的表头 (Header)
                shutil.copyfileobj(f_new, f_main)

    except Exception as e:
        print(f"ERROR: 快速追加失败 {main_file_path}: {e}")

# --- 合并同起始点的合作边 (逻辑保留但暂时不调用) ---
def _aggregate_collaboration_props(group):
    combined_list = []
    total_cnt = 0
    for props_str in group:
        try:
            props_json = json.loads(props_str)
            if isinstance(props_json.get("list"), list):
                combined_list.extend(props_json["list"])
            cnt = props_json.get("cnt", 0)
            if cnt == 0 and isinstance(props_json.get("list"), list):
                total_cnt += len(props_json["list"])
            else:
                 total_cnt += cnt
        except (json.JSONDecodeError, TypeError):
            continue
    if total_cnt == 0:
        total_cnt = len(combined_list)
    new_props = {"cnt": total_cnt, "list": combined_list}
    return json.dumps(new_props)

# --- 计算增量 ---
def _calculate_all_increments(tmp_csv_dir, tmp_edg_dir, output_csv_dir,output_edg_dir):
    """
    读取 Tmp 目录，计算当年增量。
    注意：这里我们仍然需要读取 output 的部分 ID 列来做关联，
    但只读取 ID 列比全量读取要快得多。
    """
    # print(" 正在从 Tmp 目录计算增量...")

    increments = {
        "work_cites": defaultdict(int),
        "author_works": defaultdict(int),
        "author_cites": defaultdict(int),
        "topic_works": defaultdict(int),
        "topic_cites": defaultdict(int),
        "inst_works": defaultdict(int),
        "inst_cites": defaultdict(int)
    }

    try:
        # --- 加载 Tmp文件 (当年新增的) ---
        p_ref_new = os.path.join(tmp_edg_dir, "works_referenced_works_e_new.csv")
        if os.path.exists(p_ref_new):
            df_work_refs_NEW = pd.read_csv(p_ref_new, usecols=['endid'], dtype={'endid': 'Int64'})
            inc_work_cites = df_work_refs_NEW.groupby('endid').size().to_frame('new_cites')
        else:
            inc_work_cites = pd.DataFrame()

        p_wa_new = os.path.join(tmp_edg_dir, "works_authors_e_new.csv")
        if os.path.exists(p_wa_new):
            df_work_authors_NEW = pd.read_csv(p_wa_new, usecols=['startid', 'endid'], dtype={'startid': 'Int64', 'endid': 'Int64'}).rename(columns={'startid': 'WorkID', 'endid': 'AuthorID'})
        else:
            df_work_authors_NEW = pd.DataFrame()

        p_wt_new = os.path.join(tmp_edg_dir, "works_topics_e_new.csv")
        if os.path.exists(p_wt_new):
            df_work_topics_NEW = pd.read_csv(p_wt_new, usecols=['startid', 'endid'], dtype={'startid': 'Int64', 'endid': 'Int64'}).rename(columns={'startid': 'WorkID', 'endid': 'TopicID'})
        else:
            df_work_topics_NEW = pd.DataFrame()

        p_auth_new = os.path.join(tmp_csv_dir, "authors_new.csv")
        if os.path.exists(p_auth_new):
            df_authors_NEW = pd.read_csv(p_auth_new, usecols=['id', 'institution_id'], dtype={'id': 'Int64', 'institution_id': str}).rename(columns={'id': 'AuthorID'})
        else:
            df_authors_NEW = pd.DataFrame()

        # --- 加载 Output 历史文件 (仅ID列) ---
        p_auth_old = os.path.join(output_csv_dir, "authors.csv")
        if os.path.exists(p_auth_old):
            df_authors_OLD = pd.read_csv(p_auth_old, usecols=['id', 'institution_id'], dtype={'id': 'Int64', 'institution_id': str}).rename(columns={'id': 'AuthorID'})
        else:
            df_authors_OLD = pd.DataFrame()

        p_wa_old = os.path.join(output_edg_dir, "works_authors_e.csv")
        if os.path.exists(p_wa_old):
            df_work_authors_OLD = pd.read_csv(p_wa_old, usecols=['startid', 'endid'], dtype={'startid': 'Int64', 'endid': 'Int64'}).rename(columns={'startid': 'WorkID', 'endid': 'AuthorID'})
        else:
            df_work_authors_OLD = pd.DataFrame()

        p_wt_old = os.path.join(output_edg_dir, "works_topics_e.csv")
        if os.path.exists(p_wt_old):
            df_work_topics_OLD = pd.read_csv(p_wt_old, usecols=['startid', 'endid'], dtype={'startid': 'Int64', 'endid': 'Int64'}).rename(columns={'startid': 'WorkID', 'endid': 'TopicID'})
        else:
            df_work_topics_OLD = pd.DataFrame()

    except Exception as e:
        # 如果读取失败（例如文件不存在），这通常是第一年，可以忽略
        # print(f" WARNING：读取增量依赖文件时遇到问题: {e} (如果是首年运行请忽略)")
        return increments

    # 合并 (内存中只保留 ID 映射，开销可控)
    df_author_inst_ALL = pd.concat([df_authors_OLD, df_authors_NEW]).drop_duplicates(subset=['AuthorID'], keep='last') if not df_authors_OLD.empty or not df_authors_NEW.empty else pd.DataFrame()
    df_work_authors_ALL = pd.concat([df_work_authors_OLD, df_work_authors_NEW]) if not df_work_authors_OLD.empty or not df_work_authors_NEW.empty else pd.DataFrame()
    df_work_topics_ALL = pd.concat([df_work_topics_OLD, df_work_topics_NEW]) if not df_work_topics_OLD.empty or not df_work_topics_NEW.empty else pd.DataFrame()

    # --- 计算逻辑 ---
    if not inc_work_cites.empty:
        increments["work_cites"] = inc_work_cites.to_dict()['new_cites']

    if not df_work_authors_NEW.empty:
        increments["author_works"] = df_work_authors_NEW.groupby('AuthorID').size().to_dict()

    if not df_work_topics_NEW.empty:
        increments["topic_works"] = df_work_topics_NEW.groupby('TopicID').size().to_dict()

    if not df_work_authors_NEW.empty and not df_author_inst_ALL.empty:
        df_work_inst_NEW = df_work_authors_NEW.merge(df_author_inst_ALL, on='AuthorID')
        df_work_inst_NEW_unique = df_work_inst_NEW.drop_duplicates(subset=['WorkID', 'institution_id'])
        increments["inst_works"] = df_work_inst_NEW_unique.groupby('institution_id').size().to_dict()

    if not df_work_authors_ALL.empty and not inc_work_cites.empty:
        df_merged_ac = df_work_authors_ALL.merge(inc_work_cites, left_on='WorkID', right_index=True)
        increments["author_cites"] = df_merged_ac.groupby('AuthorID')['new_cites'].sum().to_dict()

    if not df_work_topics_ALL.empty and not inc_work_cites.empty:
        df_merged_tc = df_work_topics_ALL.merge(inc_work_cites, left_on='WorkID', right_index=True)
        increments["topic_cites"] = df_merged_tc.groupby('TopicID')['new_cites'].sum().to_dict()

    if not df_work_authors_ALL.empty and not df_author_inst_ALL.empty and not inc_work_cites.empty:
        df_work_inst_ALL = df_work_authors_ALL.merge(df_author_inst_ALL, on='AuthorID')
        df_work_inst_ALL_unique = df_work_inst_ALL.drop_duplicates(subset=['WorkID', 'institution_id'])
        df_merged_ic = df_work_inst_ALL_unique.merge(inc_work_cites, left_on='WorkID', right_index=True)
        increments["inst_cites"] = df_merged_ic.groupby('institution_id')['new_cites'].sum().to_dict()

    return increments

INTEGER_FORMAT_COLUMNS = ("cited_by_count", "works_count", "institution_id")


def _to_int(value, default=0):
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _format_optional_int(value):
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if value == "":
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError, OverflowError):
        return value


# --- 更新逻辑 (拆分为：更新旧数据 + 追加新数据) ---
def _update_and_append(output_path, tmp_path, id_col, counts_increments):
    """
    1. 如果有增量：读取主文件 -> 更新计数 -> 写回主文件 (只涉及旧数据，速度快)
    2. 如果有新文件：直接二进制追加到主文件
    """
    has_updates = any(bool(v) for v in counts_increments.values())

    if has_updates and os.path.exists(output_path):
        try:
            df_main = pd.read_csv(output_path)
            if not df_main.empty:
                if df_main[id_col].duplicated().any():
                    df_main = df_main.drop_duplicates(subset=[id_col], keep='first')
                df_main = df_main.set_index(id_col)

                for count_name, inc_dict in counts_increments.items():
                    if not inc_dict:
                        continue
                    inc_series = pd.Series(inc_dict, name=count_name).fillna(0).astype(int)

                    if count_name not in df_main.columns:
                        df_main[count_name] = 0

                    base_series = pd.to_numeric(df_main[count_name], errors='coerce').fillna(0)
                    df_main[count_name] = base_series.add(inc_series, fill_value=0).fillna(0).round().astype('int64')

                df_main = df_main.reset_index()
                for column_name in INTEGER_FORMAT_COLUMNS:
                    if column_name in df_main.columns:
                        df_main[column_name] = df_main[column_name].map(_format_optional_int)
                df_main.to_csv(output_path, index=False)
        except Exception as e:
            print(f"ERROR: 更新统计值失败 {output_path}: {e}")

    if tmp_path and os.path.exists(tmp_path):
        _fast_append_csv(output_path, tmp_path)


def _update_vertex_properties_and_append(output_path, tmp_path, id_col, counts_increments):
    has_updates = any(bool(v) for v in counts_increments.values())

    if has_updates and os.path.exists(output_path):
        temp_path = f"{output_path}.tmp_vertex_update"
        try:
            with open(output_path, 'r', encoding='utf-8', newline='', buffering=IO_BUF) as f_in, \
                 open(temp_path, 'w', encoding='utf-8', newline='', buffering=IO_BUF) as f_out:
                reader = csv.DictReader(f_in)
                writer = csv.DictWriter(f_out, fieldnames=[id_col, "properties"])
                writer.writeheader()
                for row in reader:
                    row_id_raw = row.get(id_col, "")
                    row_id = _to_int(row_id_raw, default=None)
                    props_str = row.get("properties", "")
                    try:
                        props = json.loads(props_str) if props_str else {}
                    except (json.JSONDecodeError, TypeError):
                        writer.writerow({id_col: row_id_raw, "properties": props_str})
                        continue
                    if not isinstance(props, dict):
                        writer.writerow({id_col: row_id_raw, "properties": props_str})
                        continue

                    if row_id is not None:
                        for count_name, inc_dict in counts_increments.items():
                            if not inc_dict:
                                continue
                            inc_value = inc_dict.get(row_id, inc_dict.get(str(row_id), 0))
                            if inc_value:
                                props[count_name] = _to_int(props.get(count_name), 0) + _to_int(inc_value, 0)

                    writer.writerow({
                        id_col: row_id_raw,
                        "properties": json.dumps(props, ensure_ascii=False)
                    })
            os.replace(temp_path, output_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            print(f"ERROR: 更新顶点属性失败 {output_path}: {e}")

    if tmp_path and os.path.exists(tmp_path):
        _fast_append_csv(output_path, tmp_path)

def _append_only(output_path, tmp_path):
    """纯追加模式"""
    if tmp_path and os.path.exists(tmp_path):
        _fast_append_csv(output_path, tmp_path)

def _normalize_author_collaboration(output_edg_dir):
    """
    (废弃/搁置) 规范化合并后的 author_author_e.csv
    由于性能原因，我们在年度循环中不调用此函数。
    建议在所有生成结束后，单独运行脚本处理。
    """
    path = os.path.join(output_edg_dir, "authors_authors_e.csv") # 修正文件名拼写
    if not os.path.exists(path):
        return

    try:
        # print(f" [慢操作警告] 正在全量规范化: {os.path.basename(path)} ")
        df = pd.read_csv(path, dtype={'startid': 'Int64', 'endid': 'Int64', 'properties': str})
        df['properties'] = df['properties'].fillna('{}')

        tqdm.pandas(desc="    规范化进度")
        normalized_df = df.groupby(['startid', 'endid'])['properties'].progress_apply(_aggregate_collaboration_props).reset_index()

        normalized_df.to_csv(path, index=False)
    except Exception as e:
        print(f"ERROR：无法规范化 {path}: {e}")

# --- 清空 Tmp ---
def clear_tmp_files(tmp_path):
    try:
        if os.path.exists(tmp_path):
            shutil.rmtree(tmp_path)
        # 重建目录结构
        os.makedirs(os.path.join(tmp_path, "csv-files"), exist_ok=True)
        os.makedirs(os.path.join(tmp_path, "document"), exist_ok=True)
        os.makedirs(os.path.join(tmp_path, "vector"), exist_ok=True)
        os.makedirs(os.path.join(tmp_path, "graph_vertices"), exist_ok=True)
        os.makedirs(os.path.join(tmp_path, "graph_edges"), exist_ok=True)
    except Exception as e:
        print(f"ERROR：无法清空 Tmp 目录: {e}")

# --- 主函数 ---
def run_annual_update(output_path, tmp_path):

    output_csv_dir = os.path.join(output_path, "csv-files")
    output_vtx_dir = os.path.join(output_path, "graph_vertices")
    output_edg_dir = os.path.join(output_path, "graph_edges")
    output_doc_dir = os.path.join(output_path, "document")
    output_vec_dir = os.path.join(output_path, "vector")

    tmp_csv_dir = os.path.join(tmp_path, "csv-files")
    tmp_vtx_dir = os.path.join(tmp_path, "graph_vertices")
    tmp_edg_dir = os.path.join(tmp_path, "graph_edges")
    tmp_doc_dir = os.path.join(tmp_path, "document")
    tmp_vec_dir = os.path.join(tmp_path, "vector")

    # 1. 计算增量
    increments = _calculate_all_increments(tmp_csv_dir, tmp_edg_dir, output_csv_dir, output_edg_dir)

    # 2. 更新 works.csv (Count + Append)
    _update_and_append(
        output_path=os.path.join(output_csv_dir, "works.csv"),
        tmp_path=os.path.join(tmp_csv_dir, "works_new.csv"),
        id_col='id',
        counts_increments={"cited_by_count": increments["work_cites"]}
    )
    _update_vertex_properties_and_append(
        output_path=os.path.join(output_vtx_dir, "works_v.csv"),
        tmp_path=os.path.join(tmp_vtx_dir, "works_v_new.csv"),
        id_col='id',
        counts_increments={"cited_by_count": increments["work_cites"]}
    )

    # 3. 更新 authors.csv
    _update_and_append(
        output_path=os.path.join(output_csv_dir, "authors.csv"),
        tmp_path=os.path.join(tmp_csv_dir, "authors_new.csv"),
        id_col='id',
        counts_increments={
            "works_count": increments["author_works"],
            "cited_by_count": increments["author_cites"]
        }
    )
    _update_vertex_properties_and_append(
        output_path=os.path.join(output_vtx_dir, "authors_v.csv"),
        tmp_path=os.path.join(tmp_vtx_dir, "authors_v_new.csv"),
        id_col='id',
        counts_increments={
            "works_count": increments["author_works"],
            "cited_by_count": increments["author_cites"]
        }
    )

    # 4. 更新 topics.csv
    _update_and_append(
        output_path=os.path.join(output_csv_dir, "topics.csv"),
        tmp_path=os.path.join(tmp_csv_dir, "topics_new.csv"),
        id_col='id',
        counts_increments={
            "works_count": increments["topic_works"],
            "cited_by_count": increments["topic_cites"]
        }
    )
    _update_vertex_properties_and_append(
        output_path=os.path.join(output_vtx_dir, "topics_v.csv"),
        tmp_path=os.path.join(tmp_vtx_dir, "topics_v_new.csv"),
        id_col='id',
        counts_increments={
            "works_count": increments["topic_works"],
            "cited_by_count": increments["topic_cites"]
        }
    )

    # 5. 更新 Institutions (注意：tmp_path=None 修复)
    _update_and_append(
        output_path=os.path.join(output_csv_dir, "institutions.csv"),
        tmp_path=None,
        id_col='id',
        counts_increments={
            "works_count": increments["inst_works"],
            "cited_by_count": increments["inst_cites"]
        }
    )

    # 6. 追加各种边
    _append_only(os.path.join(output_edg_dir, "works_authors_e.csv"), os.path.join(tmp_edg_dir, "works_authors_e_new.csv"))
    _append_only(os.path.join(output_edg_dir, "works_topics_e.csv"), os.path.join(tmp_edg_dir, "works_topics_e_new.csv"))
    _append_only(os.path.join(output_edg_dir, "works_referenced_works_e.csv"), os.path.join(tmp_edg_dir, "works_referenced_works_e_new.csv"))

    # 修正：追加作者合作边 (修复文件名拼写 authors_authors_e_new.csv)
    _append_only(os.path.join(output_edg_dir, "authors_authors_e.csv"), os.path.join(tmp_edg_dir, "authors_authors_e_new.csv"))

    # 追加文档和向量
    _append_only(os.path.join(output_doc_dir, "authors_doc.csv"), os.path.join(tmp_doc_dir, "authors_doc_new.csv"))
    _append_only(os.path.join(output_doc_dir, "works_doc.csv"), os.path.join(tmp_doc_dir, "works_doc_new.csv"))
    _append_only(os.path.join(output_vec_dir, "works_vec.csv"), os.path.join(tmp_vec_dir, "works_vec_new.csv"))
    _append_only(os.path.join(output_vec_dir, "topics_vec.csv"), os.path.join(tmp_vec_dir, "topics_vec_new.csv"))

    # 7. 规范化步骤 (已禁用)
    # _normalize_author_collaboration(output_edg_dir)
