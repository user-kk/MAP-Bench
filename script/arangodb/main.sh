#!/bin/bash

set -euo pipefail

# 配置

username=root
password=linux123
database=openalex_test # arangodb的数据库名称
thread_num=1 # 导入时的线程数 数据集大时可多开几个线程
force_rebuild=false # 是否忽略已经生成的预处理数据 重新生成预处理数据
build_dir=/tmp/openalex_bench/arangodb # 填一个空的文件夹就行 临时文件的生成目录
data_dir=/home/hyh/OpenAlex_mini_new


# 定义必要变量与函数

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

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
    [[ -f $build_dir/authors_document.jsonl ]] || python3 $script_dir/preproc/proc_doc.py $data_dir/doc/tiny_authors_document.csv -o $build_dir/authors_document.jsonl
    [[ -f $build_dir/works_document.jsonl ]] || python3 $script_dir/preproc/proc_doc.py $data_dir/doc/tiny_works_document_cleaned.csv -o $build_dir/works_document.jsonl

    # 预处理图
    [[ -f $build_dir/author_v.jsonl ]] || python3 $script_dir/preproc/proc_graph_v.py $data_dir/graph/vertices/author_v.csv -o $build_dir/author_v.jsonl
    [[ -f $build_dir/topic_v.jsonl ]] || python3 $script_dir/preproc/proc_graph_v.py $data_dir/graph/vertices/topic_v.csv -o $build_dir/topic_v.jsonl
    [[ -f $build_dir/work_v.jsonl ]] || python3 $script_dir/preproc/proc_graph_v.py $data_dir/graph/vertices/work_v.csv -o $build_dir/work_v.jsonl

    [[ -f $build_dir/author_author_e.jsonl ]] || python3 $script_dir/preproc/proc_graph_e.py $data_dir/graph/edges/author_author_e.csv -o $build_dir/author_author_e.jsonl --from author_v --to author_v
    [[ -f $build_dir/work_author_e.jsonl ]] || python3 $script_dir/preproc/proc_graph_e.py $data_dir/graph/edges/work_author_e.csv -o $build_dir/work_author_e.jsonl --from work_v --to author_v
    [[ -f $build_dir/work_referenced_work_e.jsonl ]] || python3 $script_dir/preproc/proc_graph_e.py $data_dir/graph/edges/work_referenced_work_e.csv -o $build_dir/work_referenced_work_e.jsonl --from work_v --to work_v
    [[ -f $build_dir/work_topic_e.jsonl ]] || python3 $script_dir/preproc/proc_graph_e.py $data_dir/graph/edges/work_topic_e.csv -o $build_dir/work_topic_e.jsonl --from work_v --to topic_v

    # 预处理向量
    [[ -f $build_dir/topics_vector.jsonl ]] || python3 $script_dir/preproc/proc_vec.py $data_dir/vector/tiny_topics_vector.csv -o $build_dir/topics_vector.jsonl
    [[ -f $build_dir/works_vector.jsonl ]] || python3 $script_dir/preproc/proc_vec.py $data_dir/vector/tiny_works_vector.csv -o $build_dir/works_vector.jsonl
}


# 检测环境和预处理

check_arango_cmds

do_preproc

# 建表和导数据

arangosh --server.username "$username" --server.password "$password" --server.database "$database" --javascript.execute "$script_dir/create_schema.js"


arangoimport --overwrite true  --file "$data_dir/table/tiny_authors_cleaned.csv" --type csv --collection "author" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[id]
arangoimport --overwrite true  --file "$data_dir/table/tiny_works.csv" --type csv --collection "work" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[id]
arangoimport --overwrite true  --file "$data_dir/table/tiny_topics.csv" --type csv --collection "topic" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[id]
arangoimport --overwrite true  --file "$data_dir/table/tiny_institutions.csv" --type csv --collection "institution" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[id]
arangoimport --overwrite true  --file "$data_dir/table/tiny_institutions_geo.csv" --type csv --collection "institution_geo" --server.username "$username" --server.password "$password" --create-collection false --threads $thread_num --server.database "$database" --merge-attributes _key=[institution_id]

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

# 建立索引

arangosh --server.username "$username" --server.password "$password" --server.database "$database" --javascript.execute "$script_dir/create_index.js"

echo "---all finish---"