# -*- coding: utf-8 -*-
"""问题4：外网电价也实时波动，在波动电价下重算问题2 与问题3。

价格同样只能在 0:00 之前观测到，所以计划用此前 7 天的同一时段平均电价做
预测，而结算按附件4 的实际电价。另外算一条“已知当天全部实际电价”的方案
作为价格完全信息下的下界，用来衡量价格预测误差值多少钱。
"""
import numpy as np

from data_io import load_inputs, SOC_INIT, DISPLAY_DATES
from forecast import history_mean_forecast, pv_forecast_after, safety_margin, RELEASE_HOURS
from core import solve_plan, settle, roll_soc, emergency_runs
from p2 import run_problem2
from p3 import run_problem3


def price_forecast(ins, day):
    """此前 7 天同一时段的平均电价。"""
    return history_mean_forecast(ins.price, day)


def run_problem4_2(ins):
    """波动电价下的问题2：计划按预测电价制定，按实际电价结算。"""
    records = []
    soc = SOC_INIT
    for day in range(len(ins.dates)):
        fc_load = history_mean_forecast(ins.load, day)
        fc_pv = history_mean_forecast(ins.pv, day)
        fc_price = price_forecast(ins, day)
        plan = solve_plan(fc_load, fc_pv, fc_price, soc_start=soc, soc_end=soc)
        purchase = plan.purchase + safety_margin(ins, day)
        real = settle(ins.load[day], ins.pv[day], ins.price[day],
                      purchase, plan.charge, plan.discharge)

        records.append(dict(day=day, plan=plan, purchase=purchase, real=real,
                            charge=plan.charge, discharge=plan.discharge,
                            soc_track=plan.soc,
                            soc_start=soc, soc_end=plan.soc[-1],
                            plan_cost=float((purchase * ins.price[day]).sum()),
                            runs=emergency_runs(real.emergency)))
        soc = plan.soc[-1]
    return records


def run_problem4_3(ins, releases=RELEASE_HOURS):
    """波动电价下的问题3：光伏用附件3 预报、电价用 7 日均值预测，滚动调整。"""
    records = []
    soc = SOC_INIT
    for day in range(len(ins.dates)):
        fc_load = history_mean_forecast(ins.load, day)
        fc_price = price_forecast(ins, day)
        real_price = ins.price[day]

        base = solve_plan(fc_load, pv_forecast_after(ins, day, 0), fc_price,
                          soc_start=soc, soc_end=soc)
        base_purchase = base.purchase + safety_margin(ins, day, 0, 0)
        purchase = base_purchase.copy()
        charge = base.charge.copy()
        discharge = base.discharge.copy()

        for hour in releases[1:]:
            start = hour * 6
            soc_now = roll_soc(charge[:start], discharge[:start], soc)[-1]
            sub = solve_plan(fc_load[start:], pv_forecast_after(ins, day, hour),
                             fc_price[start:], soc_start=soc_now, soc_end=soc,
                             base_purchase=base_purchase[start:])
            purchase[start:] = sub.purchase + safety_margin(ins, day, start, hour)
            charge[start:] = sub.charge
            discharge[start:] = sub.discharge

        soc_track = roll_soc(charge, discharge, soc)
        real = settle(ins.load[day], ins.pv[day], real_price,
                      purchase, charge, discharge, purchase_plan=base_purchase)
        records.append(dict(
            day=day, base=base, base_purchase=base_purchase, purchase=purchase,
            charge=charge, discharge=discharge, soc_start=soc, soc_end=soc_track[-1],
            soc_track=soc_track, real=real,
            base_cost=float((base_purchase * real_price).sum()),
            runs=emergency_runs(real.emergency)))
        soc = soc_track[-1]
    return records


def perfect_price_bound(ins):
    """价格完全信息下的费用下界：0:00 就已知当天全部实际电价。

    这是一条不可能达到的参照线，用来衡量价格预测误差值多少钱。
    """
    total = 0.0
    soc = SOC_INIT
    for day in range(len(ins.dates)):
        fc_load = history_mean_forecast(ins.load, day)
        fc_pv = history_mean_forecast(ins.pv, day)
        plan = solve_plan(fc_load, fc_pv, ins.price[day], soc_start=soc, soc_end=soc)
        purchase = plan.purchase + safety_margin(ins, day)
        real = settle(ins.load[day], ins.pv[day], ins.price[day],
                      purchase, plan.charge, plan.discharge)
        if day >= 31:
            total += float((purchase * ins.price[day]).sum()) + real.emergency_cost
        soc = plan.soc[-1]
    return total


def summarize_problem4(ins, records42, records43, tag=""):
    span2, span3 = records42[31:], records43[31:]
    print(f"===== 问题4{tag} 汇总（2025-02-01 至 2025-12-31，实际电价结算） =====")
    e2 = sum(r["plan_cost"] for r in span2)
    m2 = sum(r["real"].emergency_cost for r in span2)
    print(f"  4-2（对应问题2）  计划购电费 {e2:14.2f} + 紧急购电费 {m2:14.2f} = {e2 + m2:14.2f} 元")
    print(f"     紧急购电量 {sum(r['real'].emergency.sum() for r in span2):14.2f} kWh")
    e3 = sum(r["real"].energy_cost for r in span3)
    d3 = sum(r["real"].deviation_cost for r in span3)
    m3 = sum(r["real"].emergency_cost for r in span3)
    print(f"  4-3（对应问题3）  购电费 {e3:14.2f} + 偏差违约费 {d3:14.2f} + 紧急购电费 {m3:14.2f} = {e3 + d3 + m3:14.2f} 元")
    print(f"     紧急购电量 {sum(r['real'].emergency.sum() for r in span3):14.2f} kWh")

    print("\n  指定日期（4-2 / 4-3 总费用）")
    for date in DISPLAY_DATES:
        r2 = next(r for r in span2 if str(ins.dates[r["day"]]) == date)
        r3 = next(r for r in span3 if str(ins.dates[r["day"]]) == date)
        print(f"   {date}   4-2 {r2['plan_cost'] + r2['real'].emergency_cost:12.2f} 元"
              f"   4-3 {r3['real'].total_cost:12.2f} 元")
    return e2 + m2, e3 + d3 + m3


if __name__ == "__main__":
    ins = load_inputs()
    summarize_problem4(ins, run_problem4_2(ins), run_problem4_3(ins))
