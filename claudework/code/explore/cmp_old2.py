# -*- coding: utf-8 -*-
"""体检旧 workspace 的 result2/result3：能量平衡、SOC 递推、列对齐、费用口径。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
import numpy as np
import openpyxl
from data_io import load_inputs, DT, N, SOC_MIN, SOC_MAX, FLOW_MAX, SOC_INIT, block_sums

OLD = Path(r"C:\workshop\mathmodel\workspaces\2026-cumcm-c\results")
ins = load_inputs()
dates = ins.dates
d0 = int(np.where(dates == np.datetime64("2025-02-01"))[0][0])
print("2025-02-01 index =", d0, "共", len(dates), "天")


def read_wide(path, sheet):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    dates_col = [r[0] for r in rows]
    body = np.array([[np.nan if v is None else float(v) for v in r[1:1 + N]] for r in rows])
    extra = [r[1 + N:1 + N + 2] for r in rows]
    return dates_col, body, extra, ws.max_column


for f, sheets in [("result2.xlsx", ["计划购电量", "充放电量", "紧急购电量"]),
                  ("result3.xlsx", ["计划购电量", "调整购电量", "充放电量", "紧急购电量"])]:
    p = OLD / f
    wb = openpyxl.load_workbook(p, data_only=True)
    print(f"\n########## {f}  sheets={wb.sheetnames}")
    for s in sheets:
        ws = wb[s]
        print(f"  -- {s}: {ws.max_row} 行 x {ws.max_column} 列")
        if ws.max_column > 10:
            hdr = [ws.cell(row=1, column=c).value for c in (1, 2, 3, 144, 145, 146, 147)]
            print("     header:", hdr)
            r2 = [ws.cell(row=2, column=c).value for c in (1, 2, 3, 144, 145, 146, 147)]
            print("     row2  :", r2)
            r3 = [ws.cell(row=335, column=c).value for c in (1, 2, 3, 144, 145, 146, 147)]
            print("     last  :", r3)

# 详细体检 result2
dc, plan, extra, _ = read_wide(OLD / "result2.xlsx", "计划购电量")
print("\n=== result2 计划购电量 逐日体检 ===")
print("行数", len(dc), "首/末日", dc[0], dc[-1])
bad_total = 0
for i in range(len(plan)):
    row = plan[i]
    tot_claim = extra[i][0]
    if tot_claim is not None and abs(np.nansum(row) - float(tot_claim)) > 0.01:
        bad_total += 1
        if bad_total <= 3:
            print(f"   {dc[i]} 行内和={np.nansum(row):.2f} 但表内全天购电量={tot_claim}")
print("全天购电量与行内和不一致的天数:", bad_total, "/", len(plan))
print("含 NaN 的日数:", int(np.isnan(plan).any(axis=1).sum()))
print("负值个数:", int((np.nan_to_num(plan) < -1e-9).sum()))
print("前3天前6段:", plan[:3, :6])
print("前3天 10:00-10:10 (idx60? 59:61):", plan[:3, 58:62])

# 执行侧：用实际负载/光伏 + 计划购电量 + 报告充放电，检查能量是否够
wb = openpyxl.load_workbook(OLD / "result2.xlsx", data_only=True)
ws = wb["充放电量"]
rows = list(ws.iter_rows(min_row=2, values_only=True))
print("\n充放电量行数:", len(rows), " 前3行:", rows[:3])
print("  ...末3行:", rows[-3:])
