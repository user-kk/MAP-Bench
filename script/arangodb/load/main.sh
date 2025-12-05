#!/bin/bash

set -euo pipefail

# 配置

username=root
password=linux123
database=openalex_test # arangodb的数据库名称
thread_num=1 # 导入时的线程数 数据集大时可多开几个线程
force_rebuild=false # 是否忽略已经生成的预处理数据 重新生成预处理数据
build_dir=/tmp/openalex_bench/arangodb # 填一个空的文件夹就行 临时预处理数据文件的生成目录
data_dir=/home/hyh/OpenAlex_mini_new

author_path=$data_dir/csv-files/authors.csv
work_path=$data_dir/csv-files/works.csv
topic_path=$data_dir/csv-files/topics.csv
institution_path=$data_dir/csv-files/institutions.csv
institution_geo_path=$data_dir/csv-files/institutions_geo.csv

author_doc_path=$data_dir/document/authors_doc.csv
work_doc_path=$data_dir/document/works_doc.csv

author_v_path=$data_dir/graph_vertices/authors_v.csv
topic_v_path=$data_dir/graph_vertices/topics_v.csv
work_v_path=$data_dir/graph_vertices/works_v.csv
author_author_e_path=$data_dir/graph_edges/authors_authors_e.csv
work_author_e_path=$data_dir/graph_edges/works_authors_e.csv
work_referenced_work_e_path=$data_dir/graph_edges/works_referenced_works_e.csv
work_topic_e_path=$data_dir/graph_edges/works_topics_e.csv

topic_vec_path=$data_dir/vector/topics_vec.csv
work_vec_path=$data_dir/vector/works_vec.csv

# 定义必要变量与函数

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)" # 获得脚本所在目录

check_arango_cmds() {
  for cmd in arangosh arangoimport python3; do
    if ! command -v "$cmd" &>/dev/null; then
      echo -e "\033[31m[ERROR] 未找到 $cmd \033[0m" >&2
    fi
  done
}                                                                                                    

do_preproc(){
    if [[ $force_rebuild == true ]]; then
        echo "重新生成预处理数据..."
        [[ -d $build_dir ]] && rm -rf "$build_dir"
        mkdir -p $build_dir
    fi
    # 预处理文档
    [[ -f $build_dir/authors_document.jsonl ]] || python3 $script_dir/preproc/proc_doc.py $author_doc_path -o $build_dir/authors_document.jsonl
    [[ -f $build_dir/works_document.jsonl ]] || python3 $script_dir/preproc/proc_doc.py $work_doc_path -o $build_dir/works_document.jsonl

    # 预处理图
    [[ -f $build_dir/author_v.jsonl ]] || python3 $script_dir/preproc/proc_graph_v.py $author_v_path -o $build_dir/author_v.jsonl
    [[ -f $build_dir/topic_v.jsonl ]] || python3 $script_dir/preproc/proc_graph_v.py $topic_v_path -o $build_dir/topic_v.jsonl
    [[ -f $build_dir/work_v.jsonl ]] || python3 $script_dir/preproc/proc_graph_v.py $work_v_path -o $build_dir/work_v.jsonl

    [[ -f $build_dir/author_author_e.jsonl ]] || python3 $script_dir/preproc/proc_graph_e.py $author_author_e_path -o $build_dir/author_author_e.jsonl --from author_v --to author_v
    [[ -f $build_dir/work_author_e.jsonl ]] || python3 $script_dir/preproc/proc_graph_e.py $work_author_e_path -o $build_dir/work_author_e.jsonl --from work_v --to author_v
    [[ -f $build_dir/work_referenced_work_e.jsonl ]] || python3 $script_dir/preproc/proc_graph_e.py $work_referenced_work_e_path -o $build_dir/work_referenced_work_e.jsonl --from work_v --to work_v
    [[ -f $build_dir/work_topic_e.jsonl ]] || python3 $script_dir/preproc/proc_graph_e.py $work_topic_e_path -o $build_dir/work_topic_e.jsonl --from work_v --to topic_v

    # 预处理向量
    [[ -f $build_dir/topics_vector.jsonl ]] || python3 $script_dir/preproc/proc_vec.py $topic_vec_path -o $build_dir/topics_vector.jsonl
    [[ -f $build_dir/works_vector.jsonl ]] || python3 $script_dir/preproc/proc_vec.py $work_vec_path -o $build_dir/works_vector.jsonl
}


# 检测环境和预处理

check_arango_cmds

do_preproc

start=$(date +%s)

# 建表和导数据

arangosh --server.username "$username" --server.password "$password" --server.database "$database" --javascript.execute "$script_dir/create_schema.js"


arangoimport --overwrite true  --file "$author_path" --type csv --collection "author" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[id]
arangoimport --overwrite true  --file "$work_path" --type csv --collection "work" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[id]
arangoimport --overwrite true  --file "$topic_path" --type csv --collection "topic" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[id]
arangoimport --overwrite true  --file "$institution_path" --type csv --collection "institution" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[id]
arangoimport --overwrite true  --file "$institution_geo_path" --type csv --collection "institution_geo" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[institution_id]

echo "关系模型导入完成"


arangoimport --overwrite true  --file "$build_dir/authors_document.jsonl" --type jsonl --collection "author_doc" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"
arangoimport --overwrite true  --file "$build_dir/works_document.jsonl" --type jsonl --collection "work_doc" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"

echo "文档模型导入完成"


arangoimport --overwrite true  --file "$build_dir/author_v.jsonl" --type jsonl --collection "author_v" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"
arangoimport --overwrite true  --file "$build_dir/topic_v.jsonl" --type jsonl --collection "topic_v" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"
arangoimport --overwrite true  --file "$build_dir/work_v.jsonl" --type jsonl --collection "work_v" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"

arangoimport --overwrite true  --file "$build_dir/author_author_e.jsonl" --type jsonl --collection "author_author_e" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"
arangoimport --overwrite true  --file "$build_dir/work_author_e.jsonl" --type jsonl --collection "work_author_e" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"
arangoimport --overwrite true  --file "$build_dir/work_referenced_work_e.jsonl" --type jsonl --collection "work_referenced_work_e" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"
arangoimport --overwrite true  --file "$build_dir/work_topic_e.jsonl" --type jsonl --collection "work_topic_e" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"

echo "图模型导入完成"


arangoimport --overwrite true  --file "$build_dir/topics_vector.jsonl" --type jsonl --collection "topic_vec" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"
arangoimport --overwrite true  --file "$build_dir/works_vector.jsonl" --type jsonl --collection "work_vec" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database"

echo "向量模型导入完成"

echo "导入数据完成，耗时：$(($(date +%s) - start)) 秒"
# 建立索引
start=$(date +%s)
arangosh --server.username "$username" --server.password "$password" --server.database "$database" --server.request-timeout 86400 --javascript.execute "$script_dir/create_index.js"
echo "创建索引完成，耗时：$(($(date +%s) - start)) 秒"
echo "---all finish---"