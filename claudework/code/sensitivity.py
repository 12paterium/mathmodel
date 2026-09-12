# -*- coding: utf-8 -*-
"""灵敏度分析：关键参数扰动对全年费用的影响。"""
import numpy as np

from data_io import load_inputs, SOC_INIT
from forecast import history_mean_forecast
from core import solve_plan, settle, ETA_CHARGE
import core

ins = load_inputs()
DAYS = range(31, 365)


def run_annual(window=7, quantile=0.8, err_window=28, terminal="cyclic", eta_charge=0.9,
               emergency_multiple=5.0, return_daily=False):
    """按给定参数跑全年问题2，返回总费用与紧急购电量。"""
    core.ETA_CHARGE = eta_charge
    plan_sum = emg_sum = emg_kwh = 0.0
    soc = SOC_INIT
    for day in range(365):
        lo = max(0, day - window)
        fc_load = ins.load[lo:day].mean(axis=0) if lo < day else ins.load[day]
        fc_pv = ins.pv[lo:day].mean(axis=0) if lo < day else ins.pv[day]
        end = soc if terminal == "cyclic" else None
        d = solve_plan(fc_load, fc_pv, ins.a1_price, soc_start=soc, soc_end=end)
        if err_window:
            e_lo = max(1, day - err_window)
            errs = np.array([(ins.load[t] - ins.load[max(0, t - window):t].mean(axis=0))
                             - (ins.pv[t] - ins.pv[max(0, t - window):t].mean(axis=0))
                             for t in range(e_lo, day)]) if e_lo < day else None
            margin = np.maximum(np.quantile(errs, quantile, axis=0), 0.0) if errs is not None else np.zeros(144)
        else:
            margin = np.zeros(144)
        buy = d.purchase + margin
        r = settle(ins.load[day], ins.pv[day], ins.a1_price, buy, d.charge, d.discharge)
        if day >= 31:
            plan_sum += float((buy * ins.a1_price).sum())
            emg_sum += (emergency_multiple / 5.0) * r.emergency_cost
            emg_kwh += r.emergency.sum()
        soc = d.soc[-1]
    core.ETA_CHARGE = 0.9
    return plan_sum + emg_sum, emg_kwh


if __name__ == "__main__":
    base_cost, base_kwh = run_annual()
    print(f"基准（7日预测 / 0.8分位 / 28日误差窗 / 日循环 / 效率0.9,1.0）: "
          f"{base_cost:12.0f} 元，紧急购电 {base_kwh:10.1f} kWh\n")

    print("1) 预测窗口")
    for w in (1, 3, 7, 14, 30):
        c, k = run_annual(window=w)
        print(f"   前 {w:2d} 日均值   {c:12.0f} 元 ({c - base_cost:+9.0f})   紧急 {k:9.1f} kWh")

    print("\n2) 安全裕度分位点")
    for q in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95):
        c, k = run_annual(quantile=q)
        print(f"   q = {q:.2f}      {c:12.0f} 元 ({c - base_cost:+9.0f})   紧急 {k:9.1f} kWh")

    print("\n3) 误差样本窗口")
    for w in (7, 14, 28, 60, 120):
        c, k = run_annual(err_window=w)
        print(f"   前 {w:3d} 日样本   {c:12.0f} 元 ({c - base_cost:+9.0f})   紧急 {k:9.1f} kWh")

    print("\n4) 收尾电量约束")
    for t in ("cyclic", "free"):
        c, k = run_annual(terminal=t, quantile=0.8)
        print(f"   {t:6s}        {c:12.0f} 元 ({c - base_cost:+9.0f})   紧急 {k:9.1f} kWh")

    print("\n5) 充电效率（放电效率固定为 1）")
    for e in (0.85, 0.9, 0.95, 1.0):
        c, k = run_annual(eta_charge=e)
        print(f"   eta_c = {e:.2f}   {c:12.0f} 元 ({c - base_cost:+9.0f})   紧急 {k:9.1f} kWh")

    print("\n6) 紧急购电价比率 m：报童公式给出最优分位点 q=1-1/m")
    for m in (2.0, 3.0, 5.0, 8.0, 10.0):
        q_opt = 1.0 - 1.0 / m
        c_fix, k_fix = run_annual(quantile=0.8, emergency_multiple=m)
        c_opt, k_opt = run_annual(quantile=q_opt, emergency_multiple=m)
        print(f"   m = {m:4.1f}  理论 q={q_opt:.3f}：{c_opt:12.0f} 元   "
              f"固定 q=0.80：{c_fix:12.0f} 元   q 取对可再省 {c_fix - c_opt:9.0f} 元")
