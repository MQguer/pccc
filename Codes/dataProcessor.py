import re
import os
import csv
import tensorflow as tf
import numpy as np
import pandas as pd

# 显示配置，便于在命令台显示完整结果
pd.set_option('display.max_columns', 10000)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 10000)

# 程序可调整的相关参数
bool_print = False           # 是否在终端print输出具体的事务工作集（预测和实际）

# 数据项的编号及记录
data_total = 1      # 出现过的数据项数量总和
data_dict = {}      # 数据项及其对应编号

table_total = 1     # 出现过的数据表数量总和
table_id = {}       # 数据表及其对应编号

data_item_hash = {}

def write_data_to_csv(X_data, y_data, filename='./Output/Text/Data_output.csv'):
    if not os.path.exists(filename):
        with open(filename, 'w+', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['input', 'output']) # 写入表头
            # 遍历每组数据
            for X_group, y_group in zip(X_data, y_data):
                # 将输入数据和输出数据转换为字符串
                input_str = ' '.join(map(str, X_group))
                output_str = ' '.join(map(str, y_group))
                # 写入CSV文件
                writer.writerow([input_str, output_str])
    else:
        with open(filename, 'a+', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # 遍历每组数据
            for X_group, y_group in zip(X_data, y_data):
                # 将输入数据和输出数据转换为字符串
                input_str = ' '.join(map(str, X_group))
                output_str = ' '.join(map(str, y_group))

                # 写入CSV文件
                writer.writerow([input_str, output_str])

    print(f"CSV 文件 '{filename}' 已写入")

def read_csv_all_data(logFile):
    global data_total
    # 读取原始数据，手动重命名各列的属性名
    colNames = ['TIME', 'UNAME', 'DBNAME', 'PID', 'HOSTPORT', 'SID', 'SLNUM', 'TAG', 'TIME2', 'VXID', 'XID', 'LTYPE', 'STATE', 'LOG', 'DETAIL', 'P', 'Q', 'R',
                'S', 'T', 'U', 'V', 'AMAME', 'BACKEND']
    # colNames = ['TIME', 'VXID', 'XID', 'LOG', 'DETAIL', 'A', 'B', 'C']
    dataset = pd.read_csv(logFile, header=None, names=colNames, dtype='str', encoding="ANSI")

    # 去除虚拟事务ID和LOG内容为空的无用日志记录，以及去掉其他不必要的列
    dataset.drop(dataset[dataset['VXID'] == ''].index, inplace=True)
    dataset.dropna(subset="VXID" ,axis=0, inplace=True)
    dataset.drop(['UNAME', 'DBNAME', 'PID', 'HOSTPORT', 'SID', 'SLNUM', 'TIME2', 'XID', 'STATE', 'P', 'Q', 'R', 'S', 'T', 'U', 'V',  'AMAME', 'BACKEND'], axis=1, inplace=True)

    # 待添加的新列数据初始化
    sql_Type = []           # 操作类型
    sql_statement = []      # WHERE子句（即查询条件，若全局查询则默认为“ALL”）
    sql_data = []           # 访问的数据项编号
    sql_Table = []          # 访问的数据表

    sql_TypeId = []         # 操作类型编号
    sql_TableId = []        # 访问的数据表编号

    sql_KeyValues = {}      # 查询条件键值对
    sql_KeyValues["w_id"] = []
    sql_KeyValues["d_id"] = []
    sql_KeyValues["c_id"] = []
    sql_KeyValues["i_id"] = []
    sql_KeyValues["other"] = []

    table_total_num = 0
    table_id_dict ={}

    # 按时间顺序排列
    # dataset.sort_values(by="TIME", ascending=True, inplace=True)

    aborted_txns = []

    for index, row in dataset.iterrows():
        if row["LTYPE"] == "ERROR" or row["TAG"] == "ROLLBACK":
            aborted_txns.append(row["VXID"])
            # print("Aborting transaction " + str(row["VXID"]))

    # 获取新列数据
    for index, row in dataset.iterrows():
        query_type = ""         # 操作类型
        table = ""              # 操作表
        query_condition = ""    # 查询条件
        data_index = -1         # 访问的数据项编号
        statement = ""          # SQL语句内容

        # 键值对
        type_id     =   0
        table_id    =   0
        w_id = 0
        d_id = 0
        c_id = 0
        i_id = 0
        other = ""

        # 删除虚拟事务ID为0的行记录
        if str(row["VXID"]) == ""  or (str(row["VXID"]).startswith("0")) or (str(row["VXID"]).endswith("/0")):
            dataset.drop(index, axis=0, inplace=True)
            # print("删除虚拟事务ID " + str(row["VXID"]))
            continue

        # 报错信息直接记录为回滚
        if row["VXID"] in aborted_txns:
            # dataset.drop(index, axis=0, inplace=True)
            # 添加获取到的信息到新表中
            query_type = "ROLLBACK"
            sql_statement.append(query_condition)
            sql_Type.append(query_type)
            sql_Table.append(table)
            sql_TypeId.append(type_id)
            sql_TableId.append(table_id)
            sql_data.append(data_index)
            sql_KeyValues["w_id"].append(w_id)
            sql_KeyValues["d_id"].append(d_id)
            sql_KeyValues["c_id"].append(c_id)
            sql_KeyValues["i_id"].append(i_id)
            sql_KeyValues["other"].append(other)
            continue

        # 获取日志信息中的SQL语句（如果没有日志信息则直接删掉这一行）
        if str(row["LOG"]).find(":") != -1:
            statement = str(row["LOG"])[(str(row["LOG"]).index(":")+2):].strip('/"').rstrip(';').rstrip()
        else:
            dataset.drop(index, axis=0, inplace=True)
            continue

        # 获取其他属性：操作类型、操作表、Where子句
        statement = re.sub(r'\s+', ' ', statement)

        # SELECT 语句分析
        if statement.upper().startswith("SELECT"):
            query_type = "SELECT"
            if(statement.upper().find("FROM") != -1):
                if (statement.upper().find("WHERE") != -1):
                    table = statement[statement.upper().index("FROM")+4: statement.upper().find("WHERE")].strip()
            if statement.find("WHERE") != -1:
                query_condition = statement[statement.index("WHERE") + 6:].strip()
                if query_condition.find("FOR UPDATE") != -1:
                    query_condition = query_condition[:  query_condition.index("FOR UPDATE")].strip()

            else:
                query_condition = "ALL"   # 如果没有查询条件，说明是全局查询，默认值为ALL

        # UPDATE 语句分析
        elif statement.upper().startswith("UPDATE"):
            query_type = "UPDATE"
            table = re.search(r'update (\w+) set', statement, re.I).group(1).strip()
            if statement.find("WHERE") != -1:
                query_condition = statement[statement.index("WHERE") + 6:].strip()
            else:
                query_condition = "ALL"     # 如果没有查询条件，说明是全局查询，默认值为ALL

        # DELETE 语句分析
        elif statement.upper().startswith("DELETE"):
            query_type = "DELETE"
            table = re.search(r'delete from (\w+) where', statement, re.I).group(1).strip()
            if statement.find("WHERE") != -1:
                query_condition = statement[statement.index("WHERE") + 6:].lstrip()
            else:
                query_condition = "ALL"    # 如果没有查询条件，说明是全局查询，默认值为ALL

        # INSERT 语句分析 TODO:其实目前还不能很好地处理Insert语句，主要只能处理UPDATE/DELETE/SELECT语句
        # elif statement.upper().startswith("INSERT"):
        #     query_type = "INSERT"
        #     insert = re.sub('\"', '', re.search(r'INTO (.*?) VALUES', statement, re.I).group(1)).strip()
        #     if insert.find("(") == -1:
        #         table = insert.split()[0].rstrip()
        #         insert_key = "ALL"
        #     else:
        #         table = insert.split("(")[0].strip()
        #         insert_key = insert.split("(")[1].split(")")[0].strip()
        #         insert_value = re.search(r"VALUES\((.*?)\)", statement).group(1).strip()
        #     query_condition = insert_key + "=" + insert_value

        # BEGIN 分析
        elif (statement.upper().startswith("BEGIN")) or (statement.upper().startswith("START")):
            query_type = "BEGIN"
        # COMMIT 分析
        elif (statement.upper().startswith("END")) or (statement.upper().startswith("COMMIT")):
            query_type = "COMMIT"
        # ROLLBACK 分析
        elif (statement.upper().startswith("ROLLBACK")) or (statement.upper().startswith("ABORT")):
            query_type = "ROLLBACK"
        # 其他
        else:
            query_type = "OTHERS"

        # 若DETAIL列（参数列）不为空，则SQL语句中必包含形如[$i]的参数，利用正则表达式匹配，将参数对应的值替换到SQL语句中
        if (row["DETAIL"] is not np.nan) and (row["DETAIL"] != "")  and (row["DETAIL"].split() != ""):
            temp_parm = row["DETAIL"].strip("\"")[row["DETAIL"].index(":", 7) + 2:].strip().strip(';').strip()  # 获取DETAIL列
            # 将temp_parm字符串转换为字典
            temp_parm_dict = {}
            for pair in temp_parm.split(","):
                key, value = pair.strip().split("=")
                temp_parm_dict[key.strip()] = value.strip()

            # 替换query_condition中的参数值
            for key, value in temp_parm_dict.items():
                query_condition = query_condition.replace(key, value)
        else:
            temp_parm = ""

        # 获取数据项编号
        if (query_condition not in data_dict) and query_condition != "":
            data_dict[query_condition] = data_total
            data_index = data_total
            data_total = data_total + 1
        elif query_condition in data_dict:
            data_index = data_dict[query_condition]
        elif query_condition == "ALL":
            data_index = 0      # 数据项编号为0表示全局访问（即没有查询条件，访问整个表的数据）
        else:
            data_index = -1     # 数据项编号为-1表示没有访问数据项

        # 获取table编号
        if table == "":
            table_id = 0
        elif table in table_id_dict:
            table_id = table_id_dict[table]
        else:
            table_total_num += 1
            table_id = table_total_num
            table_id_dict[table] = table_id

        # 获取Type编号
        if query_type == "SELECT":
            type_id = 1
        elif query_type == "UPDATE":
            type_id = 2
        elif query_type == "DELETE":
            type_id = 3
        elif query_type == "INSERT":
            type_id = 4
        elif query_type == "BEGIN":
            type_id = -1
        else:
            type_id = 0

        # 获取查询条件中的键值对
        keyValueStrs = query_condition.split("AND")
        for keyValueStr in keyValueStrs:
            if(keyValueStr.find("=") != -1):
                keyValue = keyValueStr.split("=")
                if(len(keyValue) != 2):
                    print("[ERROR] key-value: " + str(keyValue))
                else:
                    key = keyValue[0]
                    value = keyValue[1].strip().strip("\'")
                    if "w_id" in key:
                        w_id = value
                    elif "d_id" in key:
                        d_id = value
                    elif "c_id" in key:
                        c_id = value
                    elif "i_id" in key:
                        i_id = value
                    else:
                        if other == "":
                            other = query_condition
                        else:
                            other = other + " AND " + query_condition

        # 添加获取到的信息到新表中
        sql_statement.append(query_condition)
        sql_data.append(data_index)
        sql_Type.append(query_type)
        sql_TypeId.append(type_id)
        sql_Table.append(table)
        sql_TableId.append(table_id)
        sql_KeyValues["w_id"].append(w_id)
        sql_KeyValues["d_id"].append(d_id)
        sql_KeyValues["c_id"].append(c_id)
        sql_KeyValues["i_id"].append(i_id)
        sql_KeyValues["other"].append(other)

    # 添加新列，删除LOG等列以及部分行数据
    dataset["TYPE"] = sql_Type
    dataset["TABLE"] = sql_Table
    dataset["STATEMENT"] = sql_statement
    dataset["TYPEID"] = sql_TypeId
    dataset["TABLEID"] = sql_TableId
    dataset["WID"] = sql_KeyValues["w_id"]
    dataset["DID"] = sql_KeyValues["d_id"]
    dataset["CID"] = sql_KeyValues["c_id"]
    dataset["IID"] = sql_KeyValues["i_id"]
    dataset["DATA"] = sql_data
    dataset["OTHER"] = sql_KeyValues["other"]
    dataset.drop(['LOG', 'DETAIL', 'LTYPE', 'TAG'], axis=1, inplace=True)
    dataset.drop(dataset[dataset['TYPE'] == 'OTHERS'].index, inplace=True)
    dataset.drop(dataset[dataset['TYPE'] == 'INSERT'].index, inplace=True)

    dataset.reset_index(drop=True, inplace=True)

    return dataset

def getWorkingsets(dataset):
    transactions = {}
    temp_data = []
    for index, row in dataset.iterrows():
        if row["VXID"] not in transactions:
            transactions[row["VXID"]] = []
        if row["TYPEID"] != -1:
            temp_data.append(int(row["TYPEID"]))
            temp_data.append(int(row["TABLEID"]))
            temp_data.append(int(row["WID"]))
            temp_data.append(int(row["DID"]))
            temp_data.append(int(row["CID"]))
            temp_data.append(int(row["IID"]))
            transactions[row["VXID"]].append(temp_data)
            temp_data = []
    return transactions

# def getCustomerAndItem(dataset, fileName ="CustomerAndItem"):
#     new_dataset = []
#     order_index = 0
#     for index, row in dataset.iterrows():
#         if "bmsql_customer" in row["TABLE"]:
#             order_index += 1
#             c_id = str(row["STATEMENT"]).split("c_id = ")[1].strip().strip("\'")
#             temp_list = []
#             temp_list.append(order_index)
#             temp_list.append("C" + str(c_id))
#             new_dataset.append(temp_list)
#
#         if "bmsql_item" in row["TABLE"]:
#             i_id = str(row["STATEMENT"]).split("i_id = ")[1].strip().strip("\'")
#             temp_list = []
#             temp_list.append(order_index)
#             temp_list.append("I" + str(i_id))
#             new_dataset.append(temp_list)
#
#     wb = xlwt.Workbook()
#     ws = wb.add_sheet('Sheet1')
#     ws.write(0, 0, "Order_Index")
#     ws.write(0, 1, "Item_Id")
#
#     i = 0
#     for row in new_dataset:
#         i += 1
#         j = 0
#         for row_item in row:
#             ws.write(i, j, row_item)
#             j += 1
#
#     # 保存excel文件
#     wb.save('./Apriori/' + fileName + '.xls')

def get_sentences(logFile, onlySQL=False):
    # 读取原始数据，手动重命名各列的属性名
    colNames = ['TIME', 'UNAME', 'DBNAME', 'PID', 'HOSTPORT', 'SID', 'SLNUM', 'TAG', 'TIME2', 'VXID', 'XID', 'LTYPE',
                'STATE', 'LOG', 'DETAIL', 'P', 'Q', 'R',
                'S', 'T', 'U', 'V', 'AMAME', 'BACKEND']
    # colNames = ['TIME', 'VXID', 'XID', 'LOG', 'DETAIL', 'A', 'B', 'C']
    dataset = pd.read_csv(logFile, header=None, names=colNames, dtype='str', encoding="ANSI")
    # 去除虚拟事务ID和LOG内容为空的无用日志记录，以及去掉其他不必要的列
    dataset.drop(dataset[dataset['VXID'] == ''].index, inplace=True)
    dataset.dropna(subset="VXID", axis=0, inplace=True)
    dataset.drop(
        ['UNAME', 'DBNAME', 'PID', 'HOSTPORT', 'SID', 'SLNUM', 'TAG', 'TIME2', 'XID', 'STATE', 'P', 'Q', 'R', 'S', 'T',
         'U', 'V', 'AMAME', 'BACKEND'], axis=1, inplace=True)

    # 待添加的新列数据初始化
    sql_statement = []
    sql_types = []

    # 获取新列数据
    for index, row in dataset.iterrows():
        query_type = ""  # 操作类型
        data_index = -1  # 访问的数据项编号
        statement = ""  # SQL语句内容

        # 删除虚拟事务ID为0的行记录
        if str(row["VXID"]) == "" or (str(row["VXID"]).startswith("0")) or (str(row["VXID"]).endswith("/0")):
            dataset.drop(index, axis=0, inplace=True)
            # print("删除虚拟事务ID " + str(row["VXID"]))
            continue

        # 报错信息直接记录为回滚
        if row["LTYPE"] == "ERROR":
            query_type = "ROLLBACK"
            # 添加获取到的信息到新表中
            sql_statement.append(statement)
            continue

        # 获取日志信息中的SQL语句（如果没有日志信息则直接删掉这一行）
        if str(row["LOG"]).find(":") != -1:
            statement = str(row["LOG"])[(str(row["LOG"]).index(":") + 2):].strip('/"').rstrip(';').rstrip()
        else:
            dataset.drop(index, axis=0, inplace=True)
            continue

        # 获取其他属性：操作类型、操作表、Where子句
        statement = re.sub(r'\s+', ' ', statement)
        # print(statement)

        # SELECT 语句分析
        if statement.upper().startswith("SELECT"):
            query_type = "SELECT"
            if statement.find("FOR UPDATE") != -1:
                statement = statement[:  statement.index("FOR UPDATE")].strip()

        # UPDATE 语句分析
        elif statement.upper().startswith("UPDATE"):
            query_type = "UPDATE"

        # DELETE 语句分析
        elif statement.upper().startswith("DELETE"):
            query_type = "DELETE"

        # INSERT 语句分析 TODO:其实目前还不能很好地处理Insert语句，主要只能处理UPDATE/DELETE/SELECT语句
        elif statement.upper().startswith("INSERT"):
            query_type = "INSERT"

        # BEGIN 分析
        elif (statement.upper().startswith("BEGIN")) or (statement.upper().startswith("START")):
            query_type = "BEGIN"

        # COMMIT 分析
        elif (statement.upper().startswith("END")) or (statement.upper().startswith("COMMIT")):
            query_type = "COMMIT"

        # ROLLBACK 分析
        elif (statement.upper().startswith("ROLLBACK")) or (statement.upper().startswith("ABORT")):
            query_type = "ROLLBACK"

        # 其他
        else:
            query_type = "OTHERS"
            if (onlySQL):
                dataset.drop(index, axis=0, inplace=True)
                continue

        # 若DETAIL列（参数列）不为空，则SQL语句中必包含形如[$i]的参数，利用正则表达式匹配，将参数对应的值替换到SQL语句中
        if (row["DETAIL"] is not np.nan) and (row["DETAIL"] != "") and (row["DETAIL"].split() != ""):
            temp_parm = row["DETAIL"].strip("\"")[row["DETAIL"].index(":", 7) + 2:].strip().strip(
                ';').strip()  # 获取DETAIL列
            # 将temp_parm字符串转换为字典
            temp_parm_dict = {}
            for pair in temp_parm.split(","):
                key, value = pair.strip().split("=")
                temp_parm_dict[key.strip()] = value.strip()

            # 替换query_condition中的参数值
            for key, value in temp_parm_dict.items():
                statement = statement.replace(key, value)
        else:
            temp_parm = ""

        sql_types.append(query_type)
        sql_statement.append(statement)

    # 添加新列，删除LOG等列以及部分行数据
    dataset["TYPE"] = sql_types
    dataset["SENTENCE"] = sql_statement

    # dataset.sort_values(by=["TIME", "TYPE"], ascending=[True, False], inplace=True)
    if(onlySQL):
        dataset.drop(dataset[dataset['TYPE'] == 'BEGIN'].index, inplace=True)
        dataset.drop(dataset[dataset['TYPE'] == 'COMMIT'].index, inplace=True)
        dataset.drop(dataset[dataset['TYPE'] == 'ROLLBACK'].index, inplace=True)
    dataset.drop(['DETAIL', 'LOG', 'LTYPE', 'TIME', 'TYPE'], axis=1, inplace=True)

    new_LogFile = logFile.rstrip(".csv") + "_sentences.csv"
    dataset.to_csv(new_LogFile)

    return dataset

def get_transaction_info(logFile):
    dataset = read_csv_all_data(logFile)
    transaction_info = {}
    for index, row in dataset.iterrows():
        if row["VXID"] not in transaction_info:
            transaction_info[row["VXID"]] = {}
            transaction_info[row["VXID"]]["CID"] = 0
            transaction_info[row["VXID"]]["IID"] = 0
        if row["CID"] != -1 and row["CID"] != 0:
            transaction_info[row["VXID"]]["CID"] = row["CID"]
        if row["IID"] != -1 and row["IID"] != 0:
            transaction_info[row["VXID"]]["IID"] = row["IID"]
    with open("./Dataset/w2v1.txt", 'a+', encoding='utf-8') as file:
        for vxid in transaction_info:
            file.write(str(transaction_info[vxid]["CID"]) + " ")
    with open("./Dataset/w2v2.txt", 'a+', encoding='utf-8') as file:
        for vxid in transaction_info:
            file.write(str(transaction_info[vxid]["IID"]) + " ")

def get_csv_data(log_file):
    dataset =   read_csv_all_data(log_file)
    workingsets = getWorkingsets(dataset)
    X_data, y_data = [], []
    for k in range(2,3):
        for vxid in workingsets:
            temp_X, temp_y = [], []
            for i in range(0, k):
                temp_X.append(tuple(workingsets[vxid][i]))
            for j in range(k, len(workingsets[vxid])):
                temp_y.append(tuple(workingsets[vxid][j]))
            X_data.append(temp_X)
            y_data.append(temp_y)
    return X_data, y_data

if __name__ == '__main__':
    logid = 80
    for term_num in [5,10,15,20,25,30,35,40]:
        # For accumulating the conflict errors or other errors still existing in concurrency
        log_file    =   "./Dataset/Result/Transformer-" + str(term_num) + "-" + str(logid) + ".csv"
        dataset = read_csv_all_data(log_file)

        error_txn = []
        total_txn = {}
        abort_txn = []
        data_occupy = {}
        txn_occupy = {}
        error_num   =   0

        # Just for counting the number of transactions
        raw_log_file = "./Dataset/DATA-LOG-" + str(logid) + ".csv"
        raw_dataset = read_csv_all_data(raw_log_file)
        all_txn = []
        for index, row in raw_dataset.iterrows():
            if row["VXID"] not in all_txn:
                all_txn.append(row["VXID"])

        for index, row in dataset.iterrows():
            if row["VXID"] not in total_txn:
                total_txn[row["VXID"]] = 0
            if row["VXID"] not in txn_occupy:
                txn_occupy[row["VXID"]] = 0
            if row["TYPE"] == "ROLLBACK":
                if row["VXID"] not in abort_txn:
                    abort_txn.append(row["VXID"])
            if row["TYPE"] == "COMMIT" or row["TYPE"] == "ROLLBACK":
                if txn_occupy[row["VXID"]] != 0 and txn_occupy[row["VXID"]] in data_occupy:
                    data_occupy.pop(txn_occupy[row["VXID"]])
                    # print("Transaction " + str(row["VXID"]) + " pops out Data " + str(txn_occupy[row["VXID"]]) + ".")
                txn_occupy.pop(row["VXID"])
                # print("Transaction " + str(row["VXID"]) + " Ends!")
            if row["IID"] != 0:
                if row["IID"] in data_occupy and data_occupy[row["IID"]] != row["VXID"] and row["VXID"] not in error_txn:
                    error_num += 1
                    error_txn.append(row["VXID"])
                    # print("[Error] Transaction " + str(row["VXID"]) + " requires Data " + str(row["IID"]) + ", but Transaction " + str(data_occupy[row["IID"]]) + " Occupying!")
                elif row["IID"] not in data_occupy:
                    txn_occupy[row["VXID"]] = row["IID"]
                    data_occupy[row["IID"]] = row["VXID"]
                    # print("Transaction " + str(row["VXID"]) + " occupies Data " + str(row["IID"]) + ".")

        # 将TIME列转换为datetime格式
        dataset['TIME'] = pd.to_datetime(dataset['TIME'])

        # 找出最大和最小时间
        max_time = dataset['TIME'].max()
        min_time = dataset['TIME'].min()

        # 计算时间差
        execution_time = max_time - min_time

        error_num   += max((len(all_txn)-len(total_txn)), 0)
        error_num   += len(abort_txn)

        print("=================" + str(log_file) + "=================")
        print("Execution Time: " + str(execution_time))
        print("ALL Num: " + str(len(all_txn)))
        print("Total Num: " + str(len(total_txn)))
        print("Abort Num: " + str(len(abort_txn)))
        print("Total Error Num: " + str(error_num))

        if(len(total_txn) > 0):
            print("Error Rate: " + str((error_num/len(total_txn))))


