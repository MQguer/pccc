import re
from collections import defaultdict

# 初始化存储数据的字典
data = defaultdict(lambda: {'Total Num': 0, 'Accurate Type Num': 0, 'Accurate Table Num': 0, 'Accurate Customer Num': 0, 'Accurate Item Num': 0})

# 读取txt文件
with open('data.txt', 'r') as file:
    lines = file.readlines()

current_k = None

# 解析文件中的数据
for line in lines:
    k_match = re.match(r'【----------------- K = (\d+) -----------------', line)
    if k_match:
        current_k = int(k_match.group(1))
        continue

    total_num_match = re.match(r'\[i=\d+\] Total Num: (\d+)', line)
    if total_num_match:
        data[current_k]['Total Num'] += int(total_num_match.group(1))
        continue

    accurate_num_match = re.match(r'\s+Accurate (\w+) Num: (\d+)', line)
    if accurate_num_match:
        num_type = accurate_num_match.group(1)
        num_value = int(accurate_num_match.group(2))
        data[current_k][f'Accurate {num_type} Num'] += num_value

# 计算新的概率值
results = {}
for k, values in data.items():
    total_num = values['Total Num']
    if total_num > 0:
        results[k] = {
            'Total Num': total_num,
            'Accurate Type Num': (values['Accurate Type Num'], values['Accurate Type Num'] / total_num),
            'Accurate Table Num': (values['Accurate Table Num'], values['Accurate Table Num'] / total_num),
            'Accurate Customer Num': (values['Accurate Customer Num'], values['Accurate Customer Num'] / total_num),
            'Accurate Item Num': (values['Accurate Item Num'], values['Accurate Item Num'] / total_num),
        }

# 输出结果
for k, result in results.items():
    print(f"K = {k}")
    print(f"Total Num: {result['Total Num']}")
    print(f"Accurate Type Num: {result['Accurate Type Num'][0]}  {result['Accurate Type Num'][1]}")
    print(f"Accurate Table Num: {result['Accurate Table Num'][0]}  {result['Accurate Table Num'][1]}")
    print(f"Accurate Customer Num: {result['Accurate Customer Num'][0]}  {result['Accurate Customer Num'][1]}")
    print(f"Accurate Item Num: {result['Accurate Item Num'][0]}  {result['Accurate Item Num'][1]}")
    print("-------------------------------------------------")
