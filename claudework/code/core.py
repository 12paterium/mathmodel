# -*- coding: utf-8 -*-
"""微网购电与储能调度的核心模型。

储能效率口径（附录1“充放电效率为 90%”）：充入 1 kWh 只有 0.9 kWh 进电池，
放出 1 kWh 电池减少 1 kWh，完整充放一次 0.9。

模型是一条 10 分钟粒度的线性规划：以全天购电费用最小为目标，满足
功率平衡、储能容量、充放电功率、SOC 递推四类约束。计划定下来之后，
储能严格按计划充放电，实际与预测的差额全部由紧急购电（缺）或弃光（余）吸收。
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

from data_io import DT, N, FLOW_MAX, SOC_MIN, SOC_MAX, ETA, clock_label

ETA_CHARGE = ETA               # 充电效率 0.9
ETA_DISCHARGE = 1.0            # 放电效率 1.0


@dataclass
class Dispatch:
    """一天（或一天剩余时段）的调度方案，长度都是区间数 n。"""
    purchase: np.ndarray       # 计划购电量 kWh
    charge: np.ndarray         # 储能充电量 kWh
    discharge: np.ndarray      # 储能放电量 kWh
    soc: np.ndarray            # 每个区间结束时的储电量 kWh
    curtail: np.ndarray        # 弃光量 kWh
    cost: float                # 目标函数值（含终端电量残值，不等于购电费）


@dataclass
class Execution:
    """按计划执行后的实际结算结果。"""
    emergency: np.ndarray      # 紧急购电量 kWh
    curtail: np.ndarray        # 实际弃光量 kWh
    purchase_cost: float       # 计划购电费用 元
    emergency_cost: float      # 紧急购电费用 元

    @property
    def total_cost(self):
        return self.purchase_cost + self.emergency_cost


@dataclass
class Settlement:
    """带滚动的调整计划的结算结果。"""
    emergency: np.ndarray      # 紧急购电量 kWh
    curtail: np.ndarray        # 实际弃光量 kWh
    energy_cost: float         # 调整后购电量的电费 Σ p*x_adj
    deviation_cost: float      # 偏差违约费 0.5*Σ p*|x_adj - x_plan|
    emergency_cost: float      # 紧急购电费用 5*Σ p*emergency

    @property
    def total_cost(self):
        return self.energy_cost + self.deviation_cost + self.emergency_cost


def settle(load, pv, price, purchase, charge, discharge, purchase_plan=None):
    """按最终的购电量与充放电量结算。

    purchase_plan 为 None 时是问题2 口径（只按计划购电量付费）；
    否则是问题3 口径：按调整后购电量付费，另加 0.5 倍电价的偏差违约费。
    """
    supplied = purchase + pv + discharge - charge
    gap = load - supplied
    emergency = np.maximum(gap, 0.0)
    curtail = np.maximum(-gap, 0.0)
    energy_cost = float((purchase * price).sum())
    emergency_cost = float(5.0 * (emergency * price).sum())
    if purchase_plan is None:
        return Settlement(emergency, curtail, energy_cost, 0.0, emergency_cost)
    deviation = float(0.5 * (np.abs(purchase - purchase_plan) * price).sum())
    return Settlement(emergency, curtail, energy_cost, deviation, emergency_cost)


def solve_plan(load, pv, price, soc_start, soc_end=None, soc_end_value=None, base_purchase=None):
    """求解一组日前计划。

    load / pv    : 区间电量预测 kWh，长度 n
    price        : 区间电价 元/kWh，长度 n
    soc_start    : 决策时刻的储电量 kWh
    soc_end      : 若给定，强制收尾储电量等于该值（问题1 的日首尾相等）
    soc_end_value: 终端储电量的残值 元/kWh，默认取当日平均电价
    base_purchase: 若不为 None，表示这是滚动调整，x 相对上一版计划
                   base_purchase 结算：减少部分按 0.5 倍电价、增加部分按 1.5 倍电价。
    """
    n = len(load)
    if soc_end_value is None:
        soc_end_value = float(np.mean(price))

    adjusted = base_purchase is not None
    x, c, d, s, w = 0, n, 2 * n, 3 * n, 4 * n
    nx = 5 * n
    up, down = nx, nx + n if adjusted else None     # 相对基准计划的增加/减少量
    nvar = 5 * n + (2 * n if adjusted else 0)

    # ---- 目标函数 ----
    obj = np.zeros(nvar)
    obj[x:x + n] = price
    if adjusted:
        # 偏差结算：增购按 1.5 倍、减购按 0.5 倍承担违约费，
        # 两条合起来就是 p*x + 0.5*p*|x - base_purchase|
        obj[up:up + n] = 0.5 * price
        obj[down:down + n] = 0.5 * price
    obj[c:c + n] = 1e-8                    # 微量惩罚，避免同价时解不唯一
    obj[d:d + n] = 1e-8
    obj[w:w + n] = 1e-9
    obj[s + n - 1] = -soc_end_value        # 终端剩余电量按残值折算

    # ---- 等式约束：功率平衡 + SOC 递推 (+ 调整量定义 + 收尾电量) ----
    rows = 2 * n + (n if adjusted else 0) + (1 if soc_end is not None else 0)
    A = lil_matrix((rows, nvar))
    b = np.zeros(rows)
    for t in range(n):
        A[t, x + t] = 1.0
        A[t, d + t] = 1.0
        A[t, c + t] = -1.0
        A[t, w + t] = -1.0
        b[t] = load[t] - pv[t]

        A[n + t, s + t] = 1.0
        A[n + t, c + t] = -ETA_CHARGE
        A[n + t, d + t] = 1.0 / ETA_DISCHARGE
        if t == 0:
            b[n + t] = soc_start
        else:
            A[n + t, s + t - 1] = -1.0
    if adjusted:
        for t in range(n):
            A[2 * n + t, x + t] = 1.0
            A[2 * n + t, up + t] = -1.0
            A[2 * n + t, down + t] = 1.0
            b[2 * n + t] = base_purchase[t]
    if soc_end is not None:
        A[rows - 1, s + n - 1] = 1.0
        b[rows - 1] = soc_end

    # ---- 变量边界 ----
    bounds = ([(0.0, None)] * n              # 购电量非负（不允许售电）
              + [(0.0, FLOW_MAX)] * n        # 充电功率上限
              + [(0.0, FLOW_MAX)] * n        # 放电功率上限
              + [(SOC_MIN, SOC_MAX)] * n     # 储电量上下限
              + [(0.0, None)] * n)           # 弃光量
    if adjusted:
        bounds += [(0.0, None)] * (2 * n)

    res = linprog(obj, A_eq=A.tocsr(), b_eq=b, bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"线性规划求解失败：{res.message}")

    v = res.x
    return Dispatch(purchase=v[x:x + n].copy(), charge=v[c:c + n].copy(),
                    discharge=v[d:d + n].copy(), soc=v[s:s + n].copy(),
                    curtail=v[w:w + n].copy(), cost=float(res.fun))


def plan_cost(dispatch, price):
    """计划本身的购电费用，用于问题1、问题2的全天购电费口径。"""
    return float((dispatch.purchase * price).sum())


def roll_soc(charge, discharge, soc_start):
    """按充放电量推演储电量序列，返回每个区间结束时的储电量。"""
    soc = np.empty(len(charge))
    cur = soc_start
    for t in range(len(soc)):
        cur += ETA_CHARGE * charge[t] - discharge[t] / ETA_DISCHARGE
        soc[t] = cur
    return soc


def emergency_runs(emergency, threshold=1e-6):
    """把逐区间的紧急购电量合并成连续区间。

    返回 [(起始时刻, 结束时刻, 电量), ...]，时刻形如 "13:00" 和 "13:30"，
    相邻两个区间都有紧急购电时就并成一段。
    """
    active = np.flatnonzero(emergency > threshold)
    runs = []
    if len(active) == 0:
        return runs
    start = prev = int(active[0])
    for idx in list(active[1:]) + [None]:
        if idx is not None and idx == prev + 1:
            prev = idx
            continue
        runs.append((clock_label(start), clock_label(prev + 1),
                     float(emergency[start:prev + 1].sum())))
        if idx is not None:
            start = prev = idx
    return runs
