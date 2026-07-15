import os
import csv
import json
IO_BUF = 8 * 1024 * 1024
class DataWriter:
    def __init__(self, base_output_path):
        
        self.base_path = base_output_path
        
        self.csv_writers = {}  
        self.file_handles = {} 
        
        # --- 创建所有子目录 ---
        self.csv_dir = os.path.join(self.base_path, "csv-files")
        self.doc_dir = os.path.join(self.base_path, "document")
        self.vec_dir = os.path.join(self.base_path, "vector")
        self.vtx_dir = os.path.join(self.base_path, "graph_vertices")
        self.edg_dir = os.path.join(self.base_path, "graph_edges")
        
        for d in [self.csv_dir, self.doc_dir, self.vec_dir, self.vtx_dir, self.edg_dir]:
            os.makedirs(d, exist_ok=True)
            
        # --- 打开文件并写入表头 ---
        try:
            self._open_author_files()
            self._open_work_files()
            self._open_topic_files()
            self._open_author_author_edge_file()
            # print(f"--- DataWriter 已初始化，准备写入临时数据到: {self.base_path} ---")
        except Exception as e:
            print(f" ERROR: 无法初始化或写入表头: {e}")

    def _open_author_files(self):
        """写入新作者"""
        
        path_auth_rel = os.path.join(self.csv_dir, "authors_new.csv")
        headers_auth_rel = [
            "id", "display_name", "works_count", "cited_by_count",
            "last_known_institution", "works_api_url", "updated_date", "institution_id"
        ]
        f_auth_rel = open(path_auth_rel, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_auth_rel = csv.writer(f_auth_rel)
        writer_auth_rel.writerow(headers_auth_rel)
        self.csv_writers["author_relation"] = writer_auth_rel 
        self.file_handles["author_relation"] = f_auth_rel      

        path_auth_doc = os.path.join(self.doc_dir, "authors_doc_new.csv")
        headers_auth_doc = ["id", "doc"]
        f_auth_doc = open(path_auth_doc, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_auth_doc = csv.writer(f_auth_doc)
        writer_auth_doc.writerow(headers_auth_doc)
        self.csv_writers["author_doc"] = writer_auth_doc
        self.file_handles["author_doc"] = f_auth_doc

        path_auth_v = os.path.join(self.vtx_dir, "authors_v_new.csv")
        headers_auth_v = ["id", "properties"]
        f_auth_v = open(path_auth_v, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_auth_v = csv.writer(f_auth_v)
        writer_auth_v.writerow(headers_auth_v)
        self.csv_writers["author_vertex"] = writer_auth_v
        self.file_handles["author_vertex"] = f_auth_v

    def _open_work_files(self):     
        path_work_rel = os.path.join(self.csv_dir, "works_new.csv")
        headers_work_rel = [
            "id", "doi", "title", "display_name", "publication_year", "publication_date",
            "type", "cited_by_count", "is_retracted", "is_paratext", "cited_by_api_url", "language"
        ]
        f_work_rel = open(path_work_rel, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_work_rel = csv.writer(f_work_rel)
        writer_work_rel.writerow(headers_work_rel)
        self.csv_writers["work_relation"] = writer_work_rel
        self.file_handles["work_relation"] = f_work_rel

        path_work_doc = os.path.join(self.doc_dir, "works_doc_new.csv")
        headers_work_doc = ["id", "doi", "doc"]
        f_work_doc = open(path_work_doc, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_work_doc = csv.writer(f_work_doc)
        writer_work_doc.writerow(headers_work_doc)
        self.csv_writers["work_doc"] = writer_work_doc
        self.file_handles["work_doc"] = f_work_doc

        path_work_vec = os.path.join(self.vec_dir, "works_vec_new.csv")
        headers_work_vec = ["id", "doi", "vec"]
        f_work_vec = open(path_work_vec, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_work_vec = csv.writer(f_work_vec)
        writer_work_vec.writerow(headers_work_vec)
        self.csv_writers["work_vector"] = writer_work_vec
        self.file_handles["work_vector"] = f_work_vec

        path_work_v = os.path.join(self.vtx_dir, "works_v_new.csv")
        headers_work_v = ["id", "properties"]
        f_work_v = open(path_work_v, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_work_v = csv.writer(f_work_v)
        writer_work_v.writerow(headers_work_v)
        self.csv_writers["work_vertex"] = writer_work_v
        self.file_handles["work_vertex"] = f_work_v

        path_wa_e = os.path.join(self.edg_dir, "works_authors_e_new.csv")
        headers_edges = ["startid", "endid", "properties"]
        f_wa_e = open(path_wa_e, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_wa_e = csv.writer(f_wa_e)
        writer_wa_e.writerow(headers_edges)
        self.csv_writers["work_author_edge"] = writer_wa_e
        self.file_handles["work_author_edge"] = f_wa_e
        
        path_wt_e = os.path.join(self.edg_dir, "works_topics_e_new.csv")
        f_wt_e = open(path_wt_e, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_wt_e = csv.writer(f_wt_e)
        writer_wt_e.writerow(headers_edges)
        self.csv_writers["work_topic_edge"] = writer_wt_e
        self.file_handles["work_topic_edge"] = f_wt_e

        path_ww_e = os.path.join(self.edg_dir, "works_referenced_works_e_new.csv")
        f_ww_e = open(path_ww_e, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_ww_e = csv.writer(f_ww_e)
        writer_ww_e.writerow(headers_edges)
        self.csv_writers["work_work_edge"] = writer_ww_e
        self.file_handles["work_work_edge"] = f_ww_e

    def _open_topic_files(self):
        
        path_topic_rel = os.path.join(self.csv_dir, "topics_new.csv")
        headers_topic_rel = [
            "id", "display_name", "subfield_id", "subfield_display_name", "field_id",
            "field_display_name", "domain_id", "domain_display_name", "description",
            "keywords", "works_api_url", "wikipedia_id", "works_count", "cited_by_count", "updated_date"
        ]
        f_topic_rel = open(path_topic_rel, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_topic_rel = csv.writer(f_topic_rel)
        writer_topic_rel.writerow(headers_topic_rel)
        self.csv_writers["topic_relation"] = writer_topic_rel
        self.file_handles["topic_relation"] = f_topic_rel

        path_topic_vec = os.path.join(self.vec_dir, "topics_vec_new.csv")
        headers_topic_vec = ["id"]
        f_topic_vec = open(path_topic_vec, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_topic_vec = csv.writer(f_topic_vec)
        writer_topic_vec.writerow(headers_topic_vec)
        self.csv_writers["topic_vector"] = writer_topic_vec
        self.file_handles["topic_vector"] = f_topic_vec

        path_topic_v = os.path.join(self.vtx_dir, "topics_v_new.csv")
        headers_topic_v = ["id", "properties"]
        f_topic_v = open(path_topic_v, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_topic_v = csv.writer(f_topic_v)
        writer_topic_v.writerow(headers_topic_v)
        self.csv_writers["topic_vertex"] = writer_topic_v
        self.file_handles["topic_vertex"] = f_topic_v

    def _open_author_author_edge_file(self):
        """打开 'author_author_e_new.csv' 文件"""
        
        path_aa_e = os.path.join(self.edg_dir, "authors_authors_e_new.csv")
        headers_edges = ["startid", "endid", "properties"]
        f_aa_e = open(path_aa_e, 'w', encoding='utf-8', newline='', buffering=IO_BUF)
        writer_aa_e = csv.writer(f_aa_e)
        writer_aa_e.writerow(headers_edges)
        self.csv_writers["author_author_edge"] = writer_aa_e
        self.file_handles["author_author_edge"] = f_aa_e

    def write_new_author(self, full_data_package):
        try:
            rel_data = full_data_package["relation"]
            self.csv_writers["author_relation"].writerow([
                rel_data["id"], rel_data["display_name"], rel_data["works_count"],
                rel_data["cited_by_count"], rel_data["last_known_institution"],
                rel_data["works_api_url"], rel_data["updated_date"], rel_data["institution_id"]
            ])
            
            doc_data = full_data_package["doc"]
            doc_json_str = json.dumps(doc_data["doc"])
            self.csv_writers["author_doc"].writerow([
                doc_data["id"], doc_json_str
            ])

            vtx_data = full_data_package["vertex"]
            prop_json_str = json.dumps(vtx_data["properties"])
            self.csv_writers["author_vertex"].writerow([
                vtx_data["id"], prop_json_str
            ])
            
        except Exception as e:
            print(f"WARNING: 写入新作者 {full_data_package.get('id')} 时失败: {e}")

    def write_new_topic(self, topic_all_csv_row):

            try:
                topic_id = topic_all_csv_row.get("id")
                
                self.csv_writers["topic_relation"].writerow([
                    topic_all_csv_row.get("id"),
                    topic_all_csv_row.get("display_name"),
                    topic_all_csv_row.get("subfield_id"),
                    topic_all_csv_row.get("subfield_display_name"),
                    topic_all_csv_row.get("field_id"),
                    topic_all_csv_row.get("field_display_name"),
                    topic_all_csv_row.get("domain_id"),
                    topic_all_csv_row.get("domain_display_name"),
                    topic_all_csv_row.get("description"),
                    topic_all_csv_row.get("keywords"),
                    topic_all_csv_row.get("works_api_url"),
                    topic_all_csv_row.get("wikipedia_id"),
                    topic_all_csv_row.get("works_count"), 
                    topic_all_csv_row.get("cited_by_count"), 
                    topic_all_csv_row.get("updated_date")
                ])
                
                vtx_properties = {
                    "display_name": topic_all_csv_row.get("display_name"),
                    "keywords": topic_all_csv_row.get("keywords"),
                    "works_count": topic_all_csv_row.get("works_count"),
                    "cited_by_count": topic_all_csv_row.get("cited_by_count")
                }
                prop_json_str = json.dumps(vtx_properties)
                self.csv_writers["topic_vertex"].writerow([
                    topic_id, prop_json_str
                ])            
            except Exception as e:
                print(f" WARNING: 写入新主题 {topic_id} 时失败: {e}")
    def write_new_work_package(self, pkg):
        """
        写入新文章
        """
        try:
            # 写入 Work (关系, 文档, 顶点)
            rel_data = pkg["work_relation"]
            self.csv_writers["work_relation"].writerow([
                rel_data["id"], rel_data["doi"], rel_data["title"], rel_data["display_name"],
                rel_data["publication_year"], rel_data["publication_date"], rel_data["type"],
                rel_data["cited_by_count"], rel_data["is_retracted"], rel_data["is_paratext"],
                rel_data["cited_by_api_url"], rel_data["language"]
            ])
            
            doc_data = pkg["work_doc"]
            self.csv_writers["work_doc"].writerow([
                doc_data["id"], doc_data.get("doi") or rel_data.get("doi", ""), json.dumps(doc_data["doc"])
            ])
            
            vtx_data = pkg["work_vertex"]
            self.csv_writers["work_vertex"].writerow([
                vtx_data["id"], json.dumps(vtx_data["properties"])
            ])
            

            # 写入 Work-Author Edges (多条)
            for edge in pkg["work_author_edges"]:
                self.csv_writers["work_author_edge"].writerow([
                    edge["startid"], edge["endid"], json.dumps(edge["properties"])
                ])
                
            # 写入 Work-Topic Edges (多条)
            for edge in pkg["work_topic_edges"]:
                self.csv_writers["work_topic_edge"].writerow([
                    edge["startid"], edge["endid"], json.dumps(edge["properties"])
                ])

            # 写入 Work-Ref Edges (多条)
            for edge in pkg["work_ref_edges"]:
                self.csv_writers["work_work_edge"].writerow([
                    edge["startid"], edge["endid"], json.dumps(edge["properties"])
                ])

            # 写入 Author-Author Edges (多条)
            for edge in pkg["author_author_edges"]:
                self.csv_writers["author_author_edge"].writerow([
                    edge["startid"], edge["endid"], json.dumps(edge["properties"])
                ])

        except Exception as e:
            print(f"!!! [DataWriter] 警告: 写入新文章 {pkg.get('work_relation', {}).get('id')} 时失败: {e}")
    
    def write_work_vector(self, vec_data):
        """写入 works_vec.csv"""
        try:
            self.csv_writers["work_vector"].writerow([
                vec_data["id"],
                vec_data["doi"],
                vec_data["vec"]
            ])
        except Exception as e:
            print(f" WARNING: 写入 Work Vector 失败: {e}")

    def write_topic_vector(self, topic_id, vec_str):
        """写入 topics_vec.csv"""
        try:
            self.csv_writers["topic_vector"].writerow([
                topic_id,
                vec_str
            ])
        except Exception as e:
            print(f" WARNING: 写入 Topic Vector 失败: {e}")

    def close_all_files(self):

        try:
            for handle_name, file_handle in self.file_handles.items():
                file_handle.close() 
            self.file_handles = {}
            self.csv_writers = {}
        except Exception as e:
            print(f"!!! [DataWriter] 警告: 关闭文件时出错: {e}")