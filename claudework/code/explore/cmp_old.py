# -*- coding: utf-8 -*-
"""对比旧 workspace 的 result1.xlsx 与本次独立解。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
import openpyxl, numpy as np

OLD = Path(r"C:\workshop\mathmodel\workspaces\2026-cumcm-c\results\result1.xlsx")
TMP = Path(r"C:\workshop\mathmodel\claudework\data\templates\result1.xlsx")

for tag, p in [("旧结果", OLD), ("模板", TMP)]:
    if not p.exists():
        print(tag, "不存在", p); continue
    wb = openpyxl.load_workbook(p, data_only=True)
    print(f"\n########## {tag}: {p.name} sheets={wb.sheetnames}")
    for ws in wb.worksheets:
        print(f"--- {ws.title} ({ws.max_row}x{ws.max_column})")
        for r in list(range(1, 4)) + list(range(ws.max_row - 2, ws.max_row + 1)):
            print("   r%-4d" % r, [ws.cell(row=r, column=c).value for c in range(1, min(ws.max_column, 8) + 1)])
