# -*- coding: utf-8 -*-
"""问题2：负载和光伏逐日变化，允许 5 倍价紧急购电。

每天 0:00 只用此前 7 天的历史数据（附件2）取平均作为当天预测，解一条确定性
线性规划。储能严格按计划充放电，实际与预测的差额全部由紧急购电（不足）或
弃光（有余）吸收。

一个有用的恒等式：记预测误差 e_t = (实际负载-预测负载) - (实际光伏-预测光伏)，
在计划的功率平衡式下执行缺额恰好等于 e_t。也就是说紧急购电量只由预测误差
决定，与电池怎么调度无关——这正是问题3 要压的那个量。
"""
import numpy as np

from data_io import load_inputs, SOC_INIT, DISPLAY_DATES
from forecast import history_mean_forecast, safety_margin
from core import solve_plan, settle, emergency_runs


def plan_for_day(ins, day, soc, price=None, need_margin=True):
    """解出第 day 天的计划购电量与储能调度。

    先在预测曲线上解线性规划，再把安全裕度直接加到计划购电量上——裕度只影响
    购电量和弃光量，不会改变储能的充放电决策，所以可以事后叠加。
    """
    if price is None:
        price = ins.a1_price
    fc_load = history_mean_forecast(ins.load, day)
    fc_pv = history_mean_forecast(ins.pv, day)
    plan = solve_plan(fc_load, fc_pv, price, soc_start=soc, soc_end=soc)
    margin = safety_margin(ins, day) if need_margin else np.zeros(len(fc_load))
    return plan, plan.purchase + margin


def run_problem2(ins):
    """逐日滚动求解问题2，返回每天一条记录。"""
    records = []
    soc = SOC_INIT
    for day in range(len(ins.dates)):
        plan, purchase = plan_for_day(ins, day, soc)
        real = settle(ins.load[day], ins.pv[day], ins.a1_price,
                      purchase, plan.charge, plan.discharge)
        records.append(dict(
            day=day, plan=plan, purchase=purchase, real=real,
            charge=plan.charge, discharge=plan.discharge, soc_track=plan.soc,
            soc_start=soc, soc_end=plan.soc[-1],
            plan_cost=float((purchase * ins.a1_price).sum()),
            runs=emergency_runs(real.emergency),
        ))
        soc = plan.soc[-1]
    return records


def summarize_problem2(ins, records):
    """打印问题2 的汇总指标，并返回总费用。"""
    span = records[31:]                       # 交付结果从 2025-02-01 开始
    plan_kwh = sum(r["purchase"].sum() for r in span)
    plan_yuan = sum(r["plan_cost"] for r in span)
    emg_kwh = sum(r["real"].emergency.sum() for r in span)
    emg_yuan = sum(r["real"].emergency_cost for r in span)
    load_kwh = ins.load[31:].sum()

    print("===== 问题2 汇总（2025-02-01 至 2025-12-31） =====")
    print(f"  实际负载合计   {load_kwh:14.2f} kWh")
    print(f"  计划购电量合计 {plan_kwh:14.2f} kWh   费用 {plan_yuan:14.2f} 元")
    print(f"  紧急购电量合计 {emg_kwh:14.2f} kWh   费用 {emg_yuan:14.2f} 元")
    print(f"  总购电费用     {plan_yuan + emg_yuan:14.2f} 元")
    print(f"  紧急购电占负载比例 {emg_kwh / load_kwh:.3%}")
    print(f"  发生紧急购电的天数 {sum(1 for r in span if r['real'].emergency.sum() > 1e-6)} / {len(span)}")

    print("\n  指定日期")
    for date in DISPLAY_DATES:
        rec = next(r for r in span if str(ins.dates[r["day"]]) == date)
        print(f"   {date}  计划购电 {rec['purchase'].sum():10.2f} kWh"
              f"  紧急购电 {rec['real'].emergency.sum():10.2f} kWh"
              f"  费用 {rec['plan_cost'] + rec['real'].emergency_cost:12.2f} 元")
    return plan_yuan + emg_yuan


if __name__ == "__main__":
    ins = load_inputs()
    summarize_problem2(ins, run_problem2(ins))
