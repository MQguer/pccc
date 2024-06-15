import os
import dataProcessor as dp
import LSTM.LSTM as lstm
import numpy as np
import matplotlib.pyplot as plt

if __name__=="__main__":
    logFile = "./Dataset/LOG_TPCC5.csv"
    dataset = dp.read_csv_all_data(logFile)
    print(dataset)
    dataset.drop(['TYPE', 'TABLE', 'STATEMENT', 'OTHER'], axis=1, inplace=True)
    dataset.to_csv(logFile.rstrip(".csv").strip() + "_new.csv")
    k_get = 6
    k_predict = 1

    for k in range(1,6):
        X_data, y_data = lstm.getLSTMDatasets(dataset, k_get, k_predict, k, 6-k)
        model = lstm.build_lstm_model(k_get, k_predict, k, 6-k, 120)
        X_data = np.array(X_data)
        y_data = np.array(y_data)

        # 划分数据集
        split_index = int(len(X_data) * 0.8)
        X_train = X_data[:split_index]
        y_train = y_data[:split_index]
        X_test = X_data[split_index:]
        y_test = y_data[split_index:]

        # 训练模型
        history = model.fit(X_train, y_train, epochs=500, batch_size=128)
        loss = history.history['loss']
        plt.plot(range(len(loss)), loss)
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.title('Training Loss')
        plt.grid(True)
        plt.legend()

        outputs_dir = f"../Outputs/LSTM/{logFile}/"
        os.makedirs(outputs_dir, exist_ok=True)
        plt.savefig(outputs_dir + "LSTM_loss_curve_" + str(k) + ".png")

        # 模型评估
        model.evaluate(X_test, y_test)


