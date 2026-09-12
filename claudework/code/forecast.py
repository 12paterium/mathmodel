# -*- coding: utf-8 -*-
"""日前预测。

问题2 起题面没有给负载和光伏的日前预测，这里统一用**此前 7 天的平均值**：
- 负载：小区负荷主要跟作息走，7 日均值能抓住日内形状；
- 光伏：附件3 只在问题3、4 提供小时级预报，问题2 只能用历史平均。
问题3、4 的光伏改用附件3 的预报，负载仍用 7 日均值。
"""
import numpy as np

FORECAST_DAYS = 7
RELEASE_HOURS = (0, 6, 12, 18)


def history_mean_forecast(series, day, window=FORECAST_DAYS):
    """第 day 天之前 window 天的平均值；第 0 天没有历史，退化为当天实际。"""
    lo = max(0, day - window)
    if lo == day:
        return series[day].copy()
    return series[lo:day].mean(axis=0)


def pv_forecast_after(ins, day, release_hour):
    """第 release_hour 时发布的预报，对应 release_hour 之后各 10 分钟区间的预测电量。

    附件3 的“预报h小时”指发布时刻起第 h 个小时，即区间 (T+h-1, T+h]，
    所以发布时刻 6:00 的“预报1小时”正好是当天 6:00-7:00，即第 36 个十分钟区间。
    一天只关心到 24:00，因此取前 (24 - release_hour) 个小时即可。
    """
    index = RELEASE_HOURS.index(release_hour)
    hours = ins.pv_fc[day, index][: 24 - release_hour]
    return np.repeat(hours, 6)


def forecast_error(ins, day, start=0, release_hour=None):
    """第 day 天按当前预测方案逐区间的预测误差 e = 负载误差 - 光伏误差。

    e > 0 表示实际净负荷比预测高，也就是当天会缺电。release_hour 为 None 时
    光伏用此前 7 天的均值，否则用附件3 对应时刻发布的预报。
    """
    fc_load = history_mean_forecast(ins.load, day)[start:]
    fc_pv = (history_mean_forecast(ins.pv, day)[start:] if release_hour is None
             else pv_forecast_after(ins, day, release_hour))
    return (ins.load[day, start:] - fc_load) - (ins.pv[day, start:] - fc_pv)


def safety_margin(ins, day, start=0, release_hour=None, window=28, quantile=0.8):
    """区间 [start, 144) 上的安全裕度：历史预测误差的 0.8 分位点。

    紧急购电价是正常价的 5 倍。多买 1 kWh 的边际成本是 p（买多了只能弃掉），
    少买 1 kWh 的边际成本是 5p*P(缺电)，两者相等时 P(缺电) = 1/5，
    所以最优裕度恰好是误差分布的 0.8 分位点——标准的报童模型结论。
    """
    lo = max(1, day - window)
    if lo >= day:
        return np.zeros(len(ins.load[day]) - start)
    errors = np.array([forecast_error(ins, d, start, release_hour)
                       for d in range(lo, day)])
    return np.maximum(np.quantile(errors, quantile, axis=0), 0.0)
