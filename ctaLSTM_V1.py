# encoding: UTF-8

"""
基于LSTM预测的交易策略实现
"""

import pandas as pd
from pandas import Series, DataFrame
from sklearn import preprocessing
import numpy as np
import os
from sklearn.metrics import mean_squared_error
import datetime
import tensorflow as tf
from tensorflow.contrib import learn
from tensorflow.python.ops import rnn, rnn_cell
import matplotlib.pyplot as plt
import cPickle
import gzip
import math
from ctaBase import *
from ctaTemplate import CtaTemplate
# %matplotlib inline


########################################################################
class ctaLSTM_V1(CtaTemplate):
    className = 'ctaLSTM_V1'
    author = u'Feng Zipeng'

    # 策略参数
    buy_raise_score = 3.8  # 预测得分超过该值，建多仓
    sell_down_score = 2.2
    buy_down_score = 2.0
    sell_raise_score = 3.6
    zhisun = 0.0015  # 止损阈值
    zhiying = 0.0005  # 止盈阈值
    # seq_len = 5  # 用于预测的时间序列长度
    n_input = 34  # 特征数量
    n_steps = 5  # 时间序列长度
    n_hidden = 500  # 隐藏层神经元个数
    n_classes = 5  # 分类数量

    # 策略变量
    count = 0  # 用来记录接收bar数据的个数
    count_bar = 0  # 用来记录bar推送给onbar数据的个数
    bar = None
    barMinute = EMPTY_STRING
    score = 0
    class_1 = 0
    class_2 = 0
    class_3 = 0
    class_4 = 0
    class_5 = 0

    rec_price = 0
    pos_rec = 0
    position = 0
    last_minutevolume = 0  # 保存上一分钟最后一个TICK的成交量
    latest_minutevolume = 0  # 用来保存当前这一分钟最后一个tick的成交量
    DATAS = []  # 保存bar数据
    records = []

    MA_5 = EMPTY_FLOAT
    MA_12 = EMPTY_FLOAT
    MA_26 = EMPTY_FLOAT
    Dis_MA5_26 = EMPTY_FLOAT
    EMA_5 = EMPTY_FLOAT
    EMA_12 = EMPTY_FLOAT
    EMA_26 = EMPTY_FLOAT
    Dis_EMA5_26 = EMPTY_FLOAT
    Vol_MA_5 = EMPTY_FLOAT
    Vol_MA_12 = EMPTY_FLOAT
    Vol_MA_26 = EMPTY_FLOAT
    Dis_Vol_MA5_26 = EMPTY_FLOAT
    Vol_EMA_5 = EMPTY_FLOAT
    Vol_EMA_12 = EMPTY_FLOAT
    Vol_EMA_26 = EMPTY_FLOAT
    Dis_Vol_EMA5_26 = EMPTY_FLOAT
    DIFF_12_26 = EMPTY_FLOAT
    DEA_12_26 = EMPTY_FLOAT
    MACD = EMPTY_FLOAT
    boll_up = EMPTY_FLOAT
    boll_down = EMPTY_FLOAT
    b_index = EMPTY_FLOAT
    channel_width = EMPTY_FLOAT
    # mean = EMPTY_FLOAT

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'pos_rec',
               'count',
               'count_bar',
               'class_1',
               'class_2',
               'class_3',
               'class_4',
               'class_5',
               'score']

    # ----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting, filepath=None):
    # def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(ctaLSTM_V1, self).__init__(ctaEngine, setting)
        self.DATAS = []
        self.lastOrder = None
        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）

    # ----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'LSTM策略初始化')

        # initData = self.loadBar(self.initDays)
        # for bar in initData:
        #     self.onBar(bar)

        self.putEvent()

    # ----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'LSTM策略启动')
        self.putEvent()

    # ----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'LSTM策略停止')
        if self.pos > 0:
            self.sell(self.price, 1)
            self.pos_rec -= 1
        if self.pos < 0:
            self.cover(self.price, 1)
            self.pos_rec += 1

        path = "/home/chocolate/Model_LSTM-Future_20161123/daily_datas"
        self.DATAS.to_csv(path + 'datas.csv')
        self.records.to_csv(path + 'trade.csv')

        self.putEvent()

    # ----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        tickMinute = tick.datetime.minute
        self.price = tick.lastPrice   # 记录每个TICK的最新价
        self.bidprice1 = tick.bidPrice1
        self.askprice1 = tick.askPrice1

        if tickMinute != self.barMinute:
            if self.bar:
                self.bar.mean = (
                    self.bar.open + self.bar.low + self.bar.close /
                    + self.bar.high) / 4.0

                self.bar.Stockup = self.bar.openInterest - self.position
                self.position = self.bar.openInterest
                # 保存上一分钟的最后一个TICK的持仓量，方便插入下一分钟数据时计算

                self.bar.volume = self.latest_minutevolume \
                    - self.last_minutevolume
                self.last_minutevolume = self.latest_minutevolume

                # 将上一分钟的数据推送给onBar
                self.count_bar += 1  # 推送给onbar的次数+1
                # print u"当前tick时间", tick.datetime
                # print u"推送当前时刻的上一分钟", self.bar.datetime, u"数据给onbar"
                # try:
                #     # 在每次tick.minute更新时将上一分钟的bar数据推送给onbar
                self.onBar(self.bar)
                # except:
                #     pass

            bar = CtaBarData()

            bar.open = tick.lastPrice
            bar.high = tick.lastPrice
            bar.low = tick.lastPrice
            bar.close = tick.lastPrice

            bar.date = tick.date
            bar.time = tick.time
            bar.datetime = tick.datetime    # K线的时间设为第一个Tick的时间

            bar.openInterest = tick.openInterest  # 持仓量，是每一个tick的开始持仓量
            self.latest_minutevolume = tick.volume

            self.bar = bar                  # 这种写法为了减少一层访问，加快速度
            self.barMinute = tickMinute     # 更新当前的分钟

        else:                               # 否则继续累加新的K线
            bar = self.bar                  # 写法同样为了加快速度

            bar.high = max(bar.high, tick.lastPrice)
            bar.low = min(bar.low, tick.lastPrice)
            bar.close = tick.lastPrice
            bar.askpr1 = tick.askPrice1
            bar.bidpr1 = tick.bidPrice1
            bar.askvo1 = tick.askVolume1
            bar.bidvo1 = tick.bidVolume1

            # 实时记录当前这一分钟最后一个tick的成交量
            self.latest_minutevolume = tick.volume
            bar.openInterest = tick.openInterest

            if self.pos == 0:
                self.rec_price = self.price

            if self.pos > 0 and self.pos_rec > 0:

                if tick.bidPrice1 > self.rec_price:
                    # 做多的时候，实时价格高于对比价格，更新对比价格，止损系数，止盈系数。
                    self.rec_price = float(self.rec_price + tick.bidPrice1) / 2

                    if self.zhisun > 0:
                        self.zhisun = self.zhisun - 0.000006
                    if self.zhiying > 0:
                        self.zhiying = self.zhiying - 0.000005
                    # self.writeCtaLog(u'多仓更新价格' + str(self.rec_price) +
                    #     u'止损比例' + str(1 - self.zhisun) + u'止盈比例' + str(1 + self.zhiying))
                    # 更新的价格，止损，止盈。

                if tick.bidPrice1 < (1 - self.zhisun) * self.rec_price:  # 止损
                    self.sell(self.bidprice1, 1)
                    self.pos_rec -= 1
                    self.writeCtaLog(u'多仓tick' + u'止损价' + str((1 - self.zhisun) * self.rec_price))
                    self.zhisun_label = True
                    self.zhisun_bar = 0
                    self.records.append([tick.datetime, self.price, u'sell'])

                if tick.bidPrice1 > self.rec_price * (1 + self.zhiying):  # 止盈
                    self.sell(self.bidprice1, 1)
                    self.pos_rec -= 1
                    self.writeCtaLog(u'多仓tick' + u'止盈价' + str(self.rec_price * (1 + self.zhiying)))
                    self.records.append([tick.datetime, self.price, u'sell'])

            if self.pos < 0:
                if tick.askPrice1 < self.rec_price:
                    self.rec_price = float(self.rec_price + tick.askPrice1) / 2

                    if self.zhisun > 0:
                        self.zhisun = self.zhisun - 0.000006
                    if self.zhiying > 0:
                        self.zhiying = self.zhiying - 0.000005
                    # tick中和bar中更新止盈止损一致，但是比例降低。
                    # self.writeCtaLog(u'空仓更新价格' + str(self.rec_price) +
                    #     u'止损比例' + str(1 + self.zhisun) + u'止盈比例' + str(1 - self.zhiying))
                    # 更新的价格，止损，止盈。

                if tick.askPrice1 > (1 + self.zhisun) * self.rec_price:
                    # 做空的时候，实时价格高于止损线
                    self.cover(self.askprice1, 1)
                    self.pos_rec += 1
                    self.writeCtaLog(u'空仓tick' + u'止损价' + str((1 + self.zhisun) * self.rec_price))

                    self.zhisun_label = True
                    self.zhisun_bar = 0
                    self.records.append([tick.datetime, self.price, u'cover'])

                elif tick.askPrice1 < self.rec_price * (1 - self.zhiying):
                    # 做空的时候，实时价格已经低于止盈线了
                    self.cover(self.askprice1, 1)
                    self.pos_rec += 1
                    self.writeCtaLog(u'空仓tick' + u'止盈价' + str(self.rec_price * (1 - self.zhiying)))

                    self.records.append([tick.datetime, self.price, u'cover'])

        self.putEvent()

    # ---------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        # start = time.clock()
        new_data = {'close': bar.close, 'max': bar.high, 'min': bar.low,
                    'mean': bar.mean, 'pos': bar.Stockup, 'vol': bar.volume,
                    'askpr1': bar.askpr1, 'askvo1': bar.askvo1,
                    'bidpr1': bar.bidpr1, 'bidvo1': bar.bidvo1}
# 对买一价和卖一价保持和tick中同样的名称，方便后续调用进行建仓/平仓

        self.DATAS.append(new_data)
        self.count += 1
        # 接收到bar推送，记录五个数据
        self.writeCtaLog(u"onbar接收到bar推送数据，时间为:" +
                         str(bar.datetime) + str(self.count) + u'分钟')
        # 如果是第一次推送，则不接受该数据，因为第一条数据的增仓量是不对的
        if self.count_bar == 1:
            self.writeCtaLog(u"onbar第一次接受数据，数据不准确，不接收.")

        # if self.count >= 26:
        if self.count >= 6:
            datafr = pd.DataFrame(self.DATAS)
            # test_data = self.data_use(datafr)
            # 获得添加特征并整理后的时间序列数据
            seq_data = self.data_use(datafr)
            # 获得1-5分钟涨跌情况预测类别
            self.class_1, self.class_2, self.class_3,\
                self.class_4, self.class_5 = self.pred(seq_data)
            # self.writeCtaLog(u'后1-5分钟涨跌情况分别为：'+class_1+','+class_2+','+class_3+','+class_4+','+class_5)
            # self.writeCtaLog(class_1, class_2, class_3, class_4, class_5)
            # 计算加权得分
            self.score = 0.4 * self.class_1 + 0.2 * self.class_2 + \
                0.2 * self.class_3 + 0.1 * self.class_4 + 0.1 * self.class_5

            # if self.score > self.buy_raise_score:
            #     if self.pos == 0:
            #         self.buy(self.price, 1)
            #         print u'buy!', self.price
            #         self.records.append([bar.datetime, self.price])

            # if self.pos == 1:
            #     if self.score < self.sell_down_score:
            #         self.sell(self.price, 1)
            #         print u'sell', self.price
            #         self.records.append([bar.datetime, self.price])

            # if self.score < self.buy_down_score:
            #     if self.pos == 0:
            #         self.short(self.price, 1)
            #         print u'buy kong!', self.price
            #         self.records.append([bar.datetime, self.price])

            # if self.pos < 0:
            #     if self.score > self.sell_raise_score:
            #         self.cover(self.price, 1)
            #         print u'sell cover!', self.price
            #         self.records.append([bar.datetime, self.price])
            self.pos_rec_concert()  # 考虑到发出建仓/平仓信号但是没有成功交易的情况，强制更新pos_rec与pos一致

            if self.pos == 0:
                if self.score > self.buy_raise_score:
                    self.buy(self.price, 1)
                    print u'buy!', self.price
                    self.pos_rec += 1
                    self.records.append([bar.datetime, self.price])
                elif self.score < self.buy_down_score:
                    self.short(self.price, 1)
                    self.pos_rec -= 1
                    print u'buy kong!', self.price
                    self.records.append([bar.datetime, self.price])

            if self.pos == 1:
                if self.score < self.sell_down_score:
                    self.sell(self.price, 1)
                    self.pos_rec -= 1
                    print u'sell', self.price
                    self.records.append([bar.datetime, self.price])

            if self.pos == -1:
                if self.score > self.sell_raise_score:
                    self.cover(self.price, 1)
                    self.pos_rec += 1
                    print u'sell cover!', self.price
                    self.records.append([bar.datetime, self.price])

            # if self.pos == 1 and self.pos_rec > 0:
            #     self.long_pos_sell(bar)

            # if self.pos == -1 and self.pos_rec < 0:
            #     self.short_pos_cover(bar)

        # 发出状态更新事件
        self.putEvent()

    def RNN(self, x, weights, biases):

        x = tf.transpose(x, [1, 0, 2])
        x = tf.reshape(x, [-1, self.n_input])
        x = tf.split(0, self.n_steps, x)
        lstm_cell = rnn_cell.BasicLSTMCell(self.n_hidden, forget_bias=1.0)
        outputs, states = rnn.rnn(lstm_cell, x, dtype=tf.float32)
        return tf.matmul(outputs[-1], weights['out']) + biases['out']

    def pred(self, seq_data):

        tf.reset_default_graph()   # 重置流图

        xtr = tf.placeholder("float", [None, self.n_steps, self.n_input])
        # ytr = tf.placeholder("float", [None, n_classes])

        weights = {
            'out': tf.Variable(tf.random_normal([self.n_hidden,
                                                self.n_classes]))
        }
        biases = {
            'out': tf.Variable(tf.random_normal([self.n_classes]))
        }
# 获取预测值
        pred = self.RNN(xtr, weights, biases)
        saver = tf.train.Saver()
# 创建会话，加载模型
        sess_1 = tf.InteractiveSession()
        sess_2 = tf.InteractiveSession()
        sess_3 = tf.InteractiveSession()
        sess_4 = tf.InteractiveSession()
        sess_5 = tf.InteractiveSession()
        path = "/home/chocolate/Model_LSTM-Future_20161123/models"
        saver.restore(sess_1, path + "/model_1min.ckpt")
        saver.restore(sess_2, path + "/model_2min.ckpt")
        saver.restore(sess_3, path + "/model_3min.ckpt")
        saver.restore(sess_4, path + "/model_4min.ckpt")
        saver.restore(sess_5, path + "/model_5min.ckpt")
        # self.writeCtaLog(u"模型加载完毕.")
# 将当前数据代入模型，获得1-5分钟的分类类别
# 5：大涨   4：小涨   3：平稳   2：小跌   1：大跌
        pred_1 = sess_1.run(pred, feed_dict={xtr: seq_data})
        class_1 = 5 - pred_1.argmax()
        pred_2 = sess_2.run(pred, feed_dict={xtr: seq_data})
        class_2 = 5 - pred_2.argmax()
        pred_3 = sess_3.run(pred, feed_dict={xtr: seq_data})
        class_3 = 5 - pred_3.argmax()
        pred_4 = sess_4.run(pred, feed_dict={xtr: seq_data})
        class_4 = 5 - pred_4.argmax()
        pred_5 = sess_5.run(pred, feed_dict={xtr: seq_data})
        class_5 = 5 - pred_5.argmax()

        return class_1, class_2, class_3, class_4, class_5

    def data_use(self, datafr):  # 根据分钟数据进行矩阵计算

        datafr['MA_5'] = pd.rolling_mean(datafr['close'], 5)
        datafr['MA_12'] = pd.rolling_mean(datafr['close'], 12)
        datafr['MA_26'] = pd.rolling_mean(datafr['close'], 26)
    # 计算移动平均线之间的距离
        datafr['Dis_MA5_26'] = datafr['MA_5'] - datafr['MA_26']
    # 计算指数平滑移动平均线
        datafr['EMA_5'] = pd.ewma(datafr['close'], span=5)
        datafr['EMA_12'] = pd.ewma(datafr['close'], span=12)
        datafr['EMA_26'] = pd.ewma(datafr['close'], span=26)
    # 计算指数平滑移动平均线之间的距离
        datafr['Dis_EMA5_26'] = datafr['EMA_5'] - datafr['EMA_26']
    # 添加成交量的移动平均线MA
        datafr['Vol_MA_5'] = pd.rolling_mean(datafr['vol'], 5)
        datafr['Vol_MA_12'] = pd.rolling_mean(datafr['vol'], 12)
        datafr['Vol_MA_26'] = pd.rolling_mean(datafr['vol'], 26)
    # 计算成交量移动平均线之间的距离
        datafr['Dis_Vol_MA5_26'] = datafr['Vol_MA_5'] - datafr['Vol_MA_26']
    # 添加成交量的指数平滑移动平均线
        datafr['Vol_EMA_5'] = pd.ewma(datafr['vol'], span=5)
        datafr['Vol_EMA_12'] = pd.ewma(datafr['vol'], span=12)
        datafr['Vol_EMA_26'] = pd.ewma(datafr['vol'], span=26)
    # 计算指数平滑移动平均线之间的距离
        datafr['Dis_Vol_EMA5_26'] = datafr['Vol_EMA_5'] - datafr['Vol_EMA_26']
    # EMA_12是快速指数移动平均线，EMA_26是慢速指数移动平均线
    # 计算DIFF
        datafr['DIFF_12_26'] = datafr['EMA_12'] - datafr['EMA_26']
    # 计算离差平均值DEA，也就是计算离差值的指数平滑移动平均，设置为5分钟的指数平滑曲线
        datafr['DEA_12_26'] = pd.ewma(datafr['DIFF_12_26'], span=9)
    # 计算MACD值
        datafr['MACD'] = 2 * (datafr['DIFF_12_26'] - datafr['DEA_12_26'])
        datafr = datafr.fillna(0)

        MD = []
        std_sum = 0
        for j in range(len(datafr)):
            if j < 12:
                MD.append(0)
            else:
                for k in range(12):
                    std_sum += (datafr['close'].iloc[j - k] -
                                datafr['MA_12'].iloc[j - k]) ** 2
                std_sum = np.sqrt(std_sum / 12.0)
                MD.append(std_sum)
                std_sum = 0
    # 计算上轨线
        datafr['boll_up'] = datafr['MA_12'] + 2 * Series(MD)
    # 计算下轨线
        datafr['boll_down'] = datafr['MA_12'] - 2 * Series(MD)
    # 计算%b指标
        datafr['b_index'] = (datafr['close'] - datafr['boll_down']
                             ) / (datafr['boll_up'] - datafr['boll_down'])
    # 计算通道宽度
        datafr['channel_width'] = (
            datafr['boll_up'] - datafr['boll_down']) / datafr['close']

        # test_data = datafr[-1:]
        test_data = DataFrame(datafr,
                              columns=['close', 'max', 'min', 'pos',
                                       'vol', 'open', 'askpr1', 'askvo1',
                                       'bidpr1', 'bidvo1', 'MA_5', 'MA_12',
                                       'MA_26', 'Dis_MA5_26', 'EMA_5',
                                       'EMA_12', 'EMA_26', 'Dis_EMA5_26',
                                       'Vol_MA_5', 'Vol_MA_12', 'Vol_MA_26',
                                       'Dis_Vol_MA5_26', 'Vol_EMA_5',
                                       'Vol_EMA_12', 'Vol_EMA_26',
                                       'Dis_Vol_EMA5_26', 'DIFF_12_26',
                                       'DEA_12_26', 'MACD', 'boll_up',
                                       'boll_down', 'b_index',
                                       'channel_width', 'mean'])
        # 取当前时刻往前n个单位长度的数据
        # test_data = test_data.fillna(0)
        test_new_data = test_data[-5:]
        # test_new_data = test_new_data.fillna(0)
        where_are_nan = np.isnan(test_new_data)
        where_are_inf = np.isinf(test_new_data)
        test_new_data[where_are_nan] = 0
        test_new_data[where_are_inf] = 0
        # 将数据变为数组形式并标准化
        data_new_array = np.array(test_new_data)
        min_max_scaler = preprocessing.MinMaxScaler()
        data_new_array = min_max_scaler.fit_transform(data_new_array)
        # 生成n分钟序列
        seq_data = [data_new_array]
        seq_data = np.array(seq_data)
        # seq_new_5 = []
        # for j in range(len(data_new_array)):
        #     if j + 5 < len(data_new_array):
        #         seq_new_5.append(data_new_array[j:j + 5])
        # seq_data = np.array(seq_new_5)

        return seq_data

    def pos_rec_concert(self):  # pos与pos_rec不一致时进行调整。
        if self.pos != self.pos_rec:
            self.writeCtaLog(u'调整pos和pos_rec' +
                             str(self.pos) + str(self.pos_rec))
            self.pos_rec = self.pos

        if self.lastOrder is not None and self.lastOrder.status == u'未成交':
            self.cancelOrder(self.lastOrder.vtOrderID)
            self.lastOrder = None
            self.writeCtaLog(u'撤销上一单')
    # ----------------------------------------------------------------------

    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        pass

    # ----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        pass


##########################################################################

class OrderManagementDemo(CtaTemplate):
    """基于tick级别细粒度撤单追单测试demo"""

    className = 'OrderManagementDemo'
    author = u'用Python的交易员'

    # 策略参数
    initDays = 10   # 初始化数据所用的天数

    # 策略变量
    bar = None
    barMinute = EMPTY_STRING

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos']

    # ----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(OrderManagementDemo, self).__init__(ctaEngine, setting)

        self.lastOrder = None
        self.orderType = ''

    # ----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'双EMA演示策略初始化')

        initData = self.loadBar(self.initDays)
        for bar in initData:
            self.onBar(bar)

        self.putEvent()

    # ----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'双EMA演示策略启动')
        self.putEvent()

    # ----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'双EMA演示策略停止')
        self.putEvent()

    # ----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""

        # 建立不成交买单测试单
        if self.lastOrder == None:
            self.buy(tick.lastprice - 10.0, 1)

        # CTA委托类型映射
        if self.lastOrder != None and self.lastOrder.direction == u'多' and self.lastOrder.offset == u'开仓':
            self.orderType = u'买开'

        elif self.lastOrder != None and self.lastOrder.direction == u'多' and self.lastOrder.offset == u'平仓':
            self.orderType = u'买平'

        elif self.lastOrder != None and self.lastOrder.direction == u'空' and self.lastOrder.offset == u'开仓':
            self.orderType = u'卖开'

        elif self.lastOrder != None and self.lastOrder.direction == u'空' and self.lastOrder.offset == u'平仓':
            self.orderType = u'卖平'

        # 不成交，即撤单，并追单
        if self.lastOrder != None and self.lastOrder.status == u'未成交':

            self.cancelOrder(self.lastOrder.vtOrderID)
            self.lastOrder = None
        elif self.lastOrder != None and self.lastOrder.status == u'已撤销':
            # 追单并设置为不能成交

            self.sendOrder(self.orderType, self.tick.lastprice - 10, 1)
            self.lastOrder = None

    # ----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        pass

    # ----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        self.lastOrder = order

    # ----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        pass
