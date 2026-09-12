# -*- coding: utf-8 -*-
"""跑通四问，写出五个结果文件，并做数值校验。"""
import json
from pathlib import Path

import numpy as np

from data_io import load_inputs, SOC_INIT, SOC_MIN, SOC_MAX, FLOW_MAX
from p1 import solve_problem1
from p2 import run_problem2, summarize_problem2
from p3 import run_problem3, summarize_problem3, goal as goal3
from p4 import run_problem4_2, run_problem4_3, summarize_problem4
from output import write_result1, write_result2, write_result3, write_result4

RESULTS = Path(__file__).resolve().parents[1] / "results"


def check_records(ins, records, name):
    """校验执行侧的能量平衡、储电量边界与充放电功率边界。"""
    worst = dict(balance=0.0, soc=0.0, flow=0.0)
    for r in records:
        day = r["day"]
        load, pv = ins.load[day], ins.pv[day]
        supply = r["purchase"] + pv + r["discharge"] + r["real"].emergency
        demand = load + r["charge"] + r["real"].curtail
        worst["balance"] = max(worst["balance"], float(np.abs(supply - demand).max()))

        soc = r["soc_track"]
        worst["soc"] = max(worst["soc"], float(SOC_MIN - soc.min()), float(soc.max() - SOC_MAX))
        worst["flow"] = max(worst["flow"],
                            float(r["charge"].max() - FLOW_MAX),
                            float(r["discharge"].max() - FLOW_MAX),
                            float(-r["charge"].min()), float(-r["discharge"].min()))
    print(f"  [{name}] 平衡残差 {worst['balance']:.2e} kWh，"
          f"SOC 越界 {worst['soc']:.2e}，功率越界 {worst['flow']:.2e}")
    return worst


def main():
    RESULTS.mkdir(exist_ok=True)
    ins = load_inputs()

    print("########## 问题1 ##########")
    _, dispatch1 = solve_problem1()
    write_result1(ins, dispatch1)

    print("\n########## 问题2 ##########")
    records2 = run_problem2(ins)
    cost2 = summarize_problem2(ins, records2)
    write_result2(ins, records2)

    print("\n########## 问题3 ##########")
    records3 = run_problem3(ins)
    cost3 = summarize_problem3(ins, records3)
    records3_frozen = run_problem3(ins, releases=(0,))
    cost3_frozen = summarize_problem3(ins, records3_frozen, "问题3 对照（只用 0:00 预报）")
    write_result3(ins, records3)

    print("\n########## 问题4 ##########")
    records42 = run_problem4_2(ins)
    records43 = run_problem4_3(ins)
    cost42, cost43 = summarize_problem4(ins, records42, records43)
    write_result4(ins, records42, records43)

    print("\n########## 数值校验 ##########")
    check_records(ins, records2, "问题2")
    check_records(ins, records3, "问题3")
    check_records(ins, records42, "问题4-2")
    check_records(ins, records43, "问题4-3")

    summary = dict(
        problem1_purchase_kwh=float(dispatch1.purchase.sum()),
        problem1_cost=float((dispatch1.purchase * ins.a1_price).sum()),
        problem2_cost=cost2,
        problem3_cost=cost3,
        problem3_cost_no_rolling=cost3_frozen,
        problem3_rolling_gain=cost3_frozen - cost3,
        problem4_2_cost=cost42,
        problem4_3_cost=cost43,
    )
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n汇总：", json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
