import os

# 映射关系：旧编号 -> 新编号
mapping = {
    "Q14": "H1",
    "S1": "H2",
    "S2": "H3",
    "S3": "H4",
    "Q4": "H5",
    "Q2": "A1",
    "Q8": "A2",
    "S4": "A3",
    "Q3": "A4",
    "S7": "A5",
    "Q15": "A6",
    "Q5": "V1",
    "S5": "V2",
    "S6": "V3",
    "Q6": "V4",
    "Q1": "G1",
    "Q7": "G2",
    "Q12": "G3"
}

# 设置你的文件所在目录
folder = "/home/hyh/OpenAlex_mini_new/script/helmdb/query"  # 替换为你的文件夹路径

for filename in os.listdir(folder):
    name, ext = os.path.splitext(filename)
    if name.upper() in mapping:
        new_name = mapping[name.upper()] + ext
        old_path = os.path.join(folder, filename)
        new_path = os.path.join(folder, new_name)
        os.rename(old_path, new_path)
        print(f"Renamed: {filename} -> {new_name}")