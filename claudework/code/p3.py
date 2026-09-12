# -*- coding: utf-8 -*-
"""问题3：每天 0:00、6:00、12:00、18:00 各拿到一次未来 24 小时整点光伏预报，
可以据此滚动调整当天尚未执行的购电计划。

- 0:00 的预报定初始计划，并约束储能 24:00 回到 0:00 的电量；
- 6:00、12:00、18:00 的预报只用来重排该时刻之后的时段，已执行的不再改；
- 调整相对 0:00 计划结算：增购部分按 1.5 倍电价、减购部分按 0.5 倍电价承担
  违约费，两条合起来等价于  p*x_adj + 0.5*p*|x_adj - x_plan|。

子问题的目标里不含紧急购电（那部分由实际执行时的预测误差决定），所以这里
最关心的是：更好的预报究竟能把紧急购电压掉多少。
"""
import numpy as np

from data_io import load_inputs, SOC_INIT, DISPLAY_DATES
from forecast import history_mean_forecast, pv_forecast_after, safety_margin, RELEASE_HOURS
from core import solve_plan, settle, roll_soc, emergency_runs


def run_problem3(ins, releases=RELEASE_HOURS):
    """滚动求解问题3。releases 可以只给 (0,)，用来做“不滚动”的对照。"""
    records = []
    soc = SOC_INIT
    for day in range(len(ins.dates)):
        fc_load = history_mean_forecast(ins.load, day)
        price = ins.a1_price

        # ---- 0:00 初始计划 ----
        base = solve_plan(fc_load, pv_forecast_after(ins, day, 0), price,
                          soc_start=soc, soc_end=soc)
        base_purchase = base.purchase + safety_margin(ins, day, 0, 0)
        purchase = base_purchase.copy()
        charge = base.charge.copy()
        discharge = base.discharge.copy()

        # ---- 后续预报时刻的滚动调整：只重排该时刻之后的区间 ----
        for hour in releases[1:]:
            start = hour * 6
            soc_now = roll_soc(charge[:start], discharge[:start], soc)[-1]
            sub = solve_plan(fc_load[start:], pv_forecast_after(ins, day, hour),
                             price[start:], soc_start=soc_now, soc_end=soc,
                             base_purchase=base_purchase[start:])
            purchase[start:] = sub.purchase + safety_margin(ins, day, start, hour)
            charge[start:] = sub.charge
            discharge[start:] = sub.discharge

        soc_track = roll_soc(charge, discharge, soc)
        real = settle(ins.load[day], ins.pv[day], price,
                      purchase, charge, discharge, purchase_plan=base_purchase)
        records.append(dict(
            day=day, base=base, base_purchase=base_purchase, purchase=purchase,
            charge=charge, discharge=discharge,
            soc_start=soc, soc_end=soc_track[-1], soc_track=soc_track, real=real,
            base_cost=float((base_purchase * price).sum()),
            runs=emergency_runs(real.emergency),
        ))
        soc = soc_track[-1]
    return records


def goal(records):
    return sum(r["real"].total_cost for r in records[31:])


def summarize_problem3(ins, records, tag="问题3"):
    span = records[31:]
    print(f"===== {tag} 汇总（2025-02-01 至 2025-12-31） =====")
    print(f"  0:00 计划购电量合计 {sum(r['base_purchase'].sum() for r in span):14.2f} kWh"
          f"   费用 {sum(r['base_cost'] for r in span):14.2f} 元")
    print(f"  调整后购电量合计     {sum(r['purchase'].sum() for r in span):14.2f} kWh"
          f"   费用 {sum(r['real'].energy_cost for r in span):14.2f} 元")
    print(f"  偏差违约费           {sum(r['real'].deviation_cost for r in span):14.2f} 元")
    print(f"  紧急购电量           {sum(r['real'].emergency.sum() for r in span):14.2f} kWh"
          f"   费用 {sum(r['real'].emergency_cost for r in span):14.2f} 元")
    print(f"  总购电费用           {goal(records):14.2f} 元")

    print("\n  指定日期")
    for date in DISPLAY_DATES:
        rec = next(r for r in span if str(ins.dates[r["day"]]) == date)
        print(f"   {date}  计划 {rec['base_purchase'].sum():10.2f}  调整后 {rec['purchase'].sum():10.2f}"
              f"  紧急 {rec['real'].emergency.sum():10.2f} kWh"
              f"  费用 {rec['real'].total_cost:12.2f} 元")
    return goal(records)


if __name__ == "__main__":
    ins = load_inputs()
    rolling = run_problem3(ins)
    summarize_problem3(ins, rolling, "问题3（引入 6/12/18 点预报）")
    frozen = run_problem3(ins, releases=(0,))
    summarize_problem3(ins, frozen, "问题3 对照（只用 0:00 预报）")
    print(f"\n引入后续预报净收益 {goal(frozen) - goal(rolling):.2f} 元")
