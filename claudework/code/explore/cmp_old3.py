# -*- coding: utf-8 -*-
"""核对旧 result2 首日的能量平衡与 SOC 递推。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
import numpy as np
import openpyxl
from data_io import load_inputs, DT, N, SOC_MIN, SOC_MAX, FLOW_MAX, SOC_INIT, block_sums

OLD = Path(r"C:\workshop\mathmodel\workspaces\2026-cumcm-c\results")
ins = load_inputs()
d0 = int(np.where(ins.dates == np.datetime64("2025-02-01"))[0][0])

wb = openpyxl.load_workbook(OLD / "result2.xlsx", data_only=True)
ws = wb["计划购电量"]
plan = np.array([float(ws.cell(row=2, column=c).value) for c in range(2, 146)])
print("2025-02-01 计划购电量 sum =", plan.sum())

ws = wb["充放电量"]
chg = np.array([float(ws.cell(row=r, column=3).value) for r in range(2, 8)])
dis = np.array([float(ws.cell(row=r, column=4).value) for r in range(2, 8)])
print("充电块和:", chg, "合计", chg.sum())
print("放电块和:", dis, "合计", dis.sum())

load = ins.load[d0]; pv = ins.pv[d0]
print("实际负载 sum:", load.sum(), " 实际光伏 sum:", pv.sum())
print("计划购电 + 光伏 + 放电 - 负载 - 充电 =",
      plan.sum() + pv.sum() + dis.sum() - load.sum() - chg.sum(),
      " (正值=有盈余可弃, 负值=必须紧急购电)")

# SOC 递推（四舍五入到 4 位的情况下）
print("\n费用口径核对：按计划购电量结算")
cost_plan = float((plan * ins.a1_price).sum())
claim = ws2 = openpyxl.load_workbook(OLD/"result2.xlsx", data_only=True)
ws2 = claim["计划购电量"]
print("   Σ 计划购电量×附件1电价 =", cost_plan, " 表中全天购电费 =", ws2.cell(row=2, column=147).value)

# result1 复核
print("\n===== 独立重解问题1（往返0.9）对照旧 result1 =====")
