# -*- coding: utf-8 -*-
"""审阅四个附件与五个模板的结构、数值范围、对齐关系。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
import openpyxl

DATA = Path(__file__).resolve().parent.parent / 'data'

def dump(path, max_rows=14, max_cols=12):
    wb = openpyxl.load_workbook(path, data_only=True)
    print(f"\n########## {path.name} ##########")
    print("sheets:", wb.sheetnames)
    for ws in wb.worksheets:
        print(f"\n--- sheet '{ws.title}'  dims={ws.dimensions}  max_row={ws.max_row} max_col={ws.max_column}")
        for i, row in enumerate(ws.iter_rows(min_row=1, max_row=min(max_rows, ws.max_row),
                                             max_col=min(max_cols, ws.max_column), values_only=True), start=1):
            vals = ["" if v is None else (round(v, 4) if isinstance(v, float) else v) for v in row]
            print(f"  r{i:<3}", vals)

for name in ['附件1.xlsx', '附件3.xlsx', '附件4.xlsx']:
    dump(DATA / name)

# 附件2 很大，只打印结构
wb2 = openpyxl.load_workbook(DATA / '附件2.xlsx', data_only=True, read_only=True)
print("\n########## 附件2.xlsx ##########")
print("sheets:", wb2.sheetnames)
for ws in wb2.worksheets:
    print(f"--- sheet '{ws.title}' max_row={ws.max_row} max_col={ws.max_column}")
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=6, max_col=ws.max_column, values_only=True), start=1):
        vals = ["" if v is None else (round(v, 4) if isinstance(v, float) else v) for v in row[:20]]
        print(f"  r{i:<3}", vals)

print("\n\n########## 模板 附件5 ##########")
for t in ['result1.xlsx', 'result2.xlsx', 'result3.xlsx']:
    dump(DATA / 'templates' / t, max_rows=12, max_cols=8)
