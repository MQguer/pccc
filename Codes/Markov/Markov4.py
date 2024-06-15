import os.path
import numpy as np
import pandas as pd
import pickle
import dataProcessor as dp
from collections import deque
from datetime import datetime

# 显示配置，便于在命令台显示完整结果
pd.set_option('display.max_columns', 10000)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 10000)

# 程序可调整的相关参数
width   =   3           # 搜索宽度（每轮预测最多加入多少个可能的预测值）
depth   =   12           # 搜索深度（最多预测多少个元素）

bool_print = True           # 是否print输出训练和测试信息
bool_temp_file = False      # 是否生成临时文件记录转移矩阵等信息

logid = 80
model_path = '../Model/Markov/Markov_TEST_'
log_file = "../Dataset/DATA-LOG-" + str(logid) + ".csv"             # 训练和测试数据集

# 保存数据到文件
def save_to_file(filename, data):
    with open(filename, 'wb') as file:
        pickle.dump(data, file)

# 从文件读取数据并返回，若不存在文件则返回一个空字典
def load_from_file(filename):
    if os.path.exists(filename):
        with open(filename, 'rb') as file:
            data = pickle.load(file)
        return data
    else:
        empty_dict = {}
        return empty_dict

# 获取马尔科夫训练和测试所需的事务信息
def getMarkovTransactions(logFile):
    # 读取原始数据集
    dataset = dp.read_csv_all_data(logFile)
    dataset.drop(['TABLE', 'STATEMENT', 'OTHER'], axis=1, inplace=True)

    # 进行初步的事务数据提取（DATA）
    transaction_dict = {}
    for index, row in dataset.iterrows():
        if row["VXID"] not in transaction_dict:
            transaction_dict[row["VXID"]] = []
        temp_row = []
        if row["TYPEID"] != -1:
            temp_row.append(row["DATA"])
            temp_row.append(row["TYPEID"])
            temp_row.append(row["TABLEID"])
            transaction_dict[row["VXID"]].append(temp_row)
    return transaction_dict

def markovTrain(X_train, y_train):
    transition_matrix = {}
    for i in range(0, len(X_train)):
        transition_tuple = tuple(X_train[i])
        if transition_tuple in transition_matrix:
            if y_train[i] in transition_matrix[transition_tuple]:
                transition_matrix[transition_tuple][y_train[i]] += 1
            else:
                transition_matrix[transition_tuple][y_train[i]] = 1
        else:
            transition_matrix[transition_tuple] = {}
            transition_matrix[transition_tuple][y_train[i]] = 1
    if(bool_print):
        print(transition_matrix)
    return transition_matrix

def markovPredict(input_tuple, transition_matrix, allow_random=True):
    predict_list = []
    if input_tuple in transition_matrix:
        predict_list = sorted(list(transition_matrix[input_tuple].items()), key=lambda x: x[1], reverse=True)
    elif allow_random:
        if bool_print:
            print("Input tuple not present! Predicting randomly!")
        all_possibilities = {}
        values = transition_matrix.values()
        for dict in values:
            for key in dict:
                if key in all_possibilities:
                    all_possibilities[key] += dict[key]
                else:
                    all_possibilities[key] = dict[key]
        predict_list = sorted(list(all_possibilities.items()), key=lambda x: x[1], reverse=True)
    elif bool_print:
        print("Input tuple not present! Stop predicting!")
    return predict_list

if __name__=="__main__":
    # Transaction data
    transaction_dict= getMarkovTransactions(log_file)

    for k_value in range(1,12):
        # 训练集划分
        X_train = []
        y_train = []
        split_factor = 0.8
        vxids = list(transaction_dict.keys())

        txn_size    =   0
        for i in range(0, int(len(vxids) * split_factor)):
            for j in range(0, len(transaction_dict[vxids[i]]) - k_value):
                temp_X = []
                txn_size    =   max(txn_size, len(transaction_dict[vxids[i]]))
                for k in range(0, k_value):
                    temp_X.append(transaction_dict[vxids[i]][j + k][0])
                X_train.append(temp_X)
                y_train.append(transaction_dict[vxids[i]][j + k_value][0])

        # Train
        transition_matrix = markovTrain(X_train, y_train)

        # Test
        total_num = list(np.zeros(txn_size))
        correct_data = list(np.zeros(txn_size))
        correct_type = list(np.zeros(txn_size))

        for i in range(int(len(vxids) * split_factor), len(vxids)):
            current_txn = transaction_dict[vxids[i]]
            input = deque()
            for j in range(0, k_value):
                input.append(current_txn[j][0])

            loop = 0
            while loop < min(len(current_txn)-k_value, depth):
                total_num[0] += 1
                total_num[k_value+loop] += 1
                predict_list = markovPredict(tuple(input), transition_matrix)
                print(predict_list)

                if len(predict_list) > 0:
                    predicted_data = []
                    for k in range(0, min(width, len(predict_list))):
                        predicted_data.append(predict_list[k][0])
                    real_data = current_txn[k_value+loop][0]

                    if real_data in predicted_data:
                        correct_data[0]                +=  1
                        correct_data[k_value+loop]   +=  1

                    if bool_print:
                        print("第" + str(k_value+loop) + "条SQL语句")
                        print("Input: " + str(tuple(input)))
                        print("Real: " + str(real_data))
                        print("Full Txn: " + str(current_txn))
                        if real_data in predicted_data:
                            print("Predict: " + str(predicted_data) + " 正确")
                        else:
                            print("Predict: " + str(predicted_data) + " 错误")
                        print("----------------------------------------")
                else:
                    print("PREDICTION FAIL!")
                input.popleft()
                input.append(predicted_data[0])
                loop += 1

        with open("../Output/Text/" + str(logid) + "/markov_test_output.txt", 'a+',
                  encoding='utf-8') as file:
            file.write("----------------- K = " + str(k_value) + " -----------------\n")
            file.write(str(datetime.now()) + "\n")
            for i in range(0, len(total_num)):
                file.write("[i=" + str(i) + "]" + " Total Num: " + str(int(total_num[i])) + "\n")
                if total_num[i] > 0:
                    file.write("    Accurate Data Num: " + str(int(correct_data[i])) + "  " + str(
                        correct_data[i] / total_num[i]) + "\n")