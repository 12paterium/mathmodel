# -*- coding: utf-8 -*-
"""问题1：电价、负载每天相同，光伏给定预测，储能日首尾电量相等。

这是一个确定性线性规划：目标为全天购电费用最小，约束为功率平衡、
储能容量与充放电功率上限、以及 0:00 和 24:00 储电量都等于 6000 kWh。
"""
import numpy as np

from data_io import load_inputs, interval_labels, block_sums, N, SOC_INIT
from core import solve_plan, plan_cost

# 论文表1、表2 要求的展示口径
SHOW_INTERVALS = ["10:00-10:10", "12:00-12:10", "14:00-14:10",
                  "16:00-16:10", "18:00-18:10", "20:00-20:10"]
SHOW_BLOCKS = ["0:00-4:00", "4:00-8:00", "8:00-12:00",
               "12:00-16:00", "16:00-20:00", "20:00-24:00"]


def solve_problem1():
    """返回问题1 的完整调度方案。"""
    ins = load_inputs()
    labels = interval_labels()
    dispatch = solve_plan(ins.a1_load, ins.a1_pv, ins.a1_price,
                          soc_start=SOC_INIT, soc_end=SOC_INIT)

    print("===== 问题1 结果 =====")
    print("表1  指定区间购电量")
    for name in SHOW_INTERVALS:
        print(f"    {name:>12}  {dispatch.purchase[labels.index(name)]:12.4f} kWh")
    total = dispatch.purchase.sum()
    cost = plan_cost(dispatch, ins.a1_price)
    print(f"    全天购电量 {total:.4f} kWh    全天购电费 {cost:.4f} 元")

    print("表2  储能分时段充放电量与首尾储电量")
    charge = block_sums(dispatch.charge)
    discharge = block_sums(dispatch.discharge)
    for name, ch, dis in zip(SHOW_BLOCKS, charge, discharge):
        print(f"    {name:>12}  充电 {ch:10.4f}  放电 {dis:10.4f}")
    print(f"    0:00 储电量 {SOC_INIT:.4f} kWh    24:00 储电量 {dispatch.soc[-1]:.4f} kWh")
    print(f"    弃光总量 {dispatch.curtail.sum():.4f} kWh")

    resid = dispatch.purchase + ins.a1_pv + dispatch.discharge \
        - ins.a1_load - dispatch.charge - dispatch.curtail
    print(f"    平衡等式最大残差 {np.abs(resid).max():.2e} kWh")
    return ins, dispatch


if __name__ == "__main__":
    solve_problem1()
