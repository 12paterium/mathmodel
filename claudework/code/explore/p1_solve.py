# -*- coding: utf-8 -*-
"""问题1：单日确定性 LP。对比两种效率口径，并核对旧结果。"""
from __future__ import annotations
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from data_io import load_inputs, N, FLOW_MAX, SOC_MIN, SOC_MAX, SOC_INIT, interval_labels

ins = load_inputs()
price, load, pv = ins.a1_price, ins.a1_load, ins.a1_pv
print("PV>load 的区间数:", int((pv > load).sum()), " 最大净负荷:", float((load - pv).max()), " 最小净负荷:", float((load - pv).min()))
print("日购电下限(无储能, 逐段≥0 求和):", float(np.maximum(load - pv, 0).sum()), "kWh")
print("日负载总量:", float(load.sum()), " 日光伏总量:", float(pv.sum()))


def solve_p1(eta_ch, eta_dis, soc_start, soc_end):
    n = N
    nb = 5  # x, c, d, s, w
    tot = 5 * n
    x0, c0, d0, s0, w0 = 0, n, 2 * n, 3 * n, 4 * n
    obj = np.zeros(tot); obj[x0:x0 + n] = price
    A = lil_matrix((2 * n + 1, tot)); b = np.zeros(2 * n + 1)
    for t in range(n):
        A[t, x0 + t] = 1.0; A[t, c0 + t] = -1.0; A[t, d0 + t] = 1.0; A[t, w0 + t] = -1.0
        b[t] = load[t] - pv[t]
        r = n + t
        A[r, s0 + t] = 1.0; A[r, c0 + t] = -eta_ch; A[r, d0 + t] = 1.0 / eta_dis
        if t:
            A[r, s0 + t - 1] = -1.0
        else:
            b[r] = soc_start
    A[2 * n, s0 + n - 1] = 1.0; b[2 * n] = soc_end
    bounds = ([(0, None)] * n + [(0, FLOW_MAX)] * n + [(0, FLOW_MAX)] * n
              + [(SOC_MIN, SOC_MAX)] * n + [(0, None)] * n)
    res = linprog(obj, A_eq=A.tocsr(), b_eq=b, bounds=bounds, method="highs")
    assert res.status == 0, res.message
    v = res.x
    return dict(x=v[x0:x0+n], c=v[c0:c0+n], d=v[d0:d0+n], s=v[s0:s0+n], w=v[w0:w0+n], cost=float(res.fun))


LAB = interval_labels()
PICK = {i: LAB[i] for i in range(144)}
want = ["10:00-10:10", "12:00-12:10", "14:00-14:10", "16:00-16:10", "18:00-18:10", "20:00-20:10"]

for tag, (ec, ed) in {"单边0.9(往返0.81)": (0.9, 0.9), "往返0.9(单边sqrt)": (np.sqrt(0.9), np.sqrt(0.9))}.items():
    r = solve_p1(ec, ed, SOC_INIT, SOC_INIT)
    print(f"\n===== 效率口径: {tag} =====")
    for w in want:
        print(f"   {w:>12}  购电量 = {r['x'][LAB.index(w)]:10.4f} kWh")
    print(f"   全天购电量 = {r['x'].sum():.4f} kWh   全天购电费 = {r['cost']:.4f} 元")
    seg = r['c'].reshape(6, 24).sum(axis=1), r['d'].reshape(6, 24).sum(axis=1)
    for k, (a, b2) in enumerate(zip(*seg)):
        print(f"   {k*4}:00-{k*4+4}:00  充电 {a:10.4f}  放电 {b2:10.4f}")
    print(f"   0:00 SOC = {SOC_INIT}   24:00 SOC = {r['s'][-1]:.6f}")
    print(f"   弃光总量 = {r['w'].sum():.4f} kWh   购电量非零区间数 = {int((r['x']>1e-9).sum())}")
    print(f"   最大平衡残差 = {np.abs(r['x']+pv+r['d']-load-r['c']-r['w']).max():.2e}")
