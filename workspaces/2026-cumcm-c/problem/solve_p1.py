# -*- coding: utf-8 -*-
"""问题1：微网计划购电策略（线性规划模型）

决策变量（每10分钟一段，共144段）：
  b_k: 从电网购电功率 (kW)
  c_k: 储能充电功率 (kW)
  d_k: 储能放电功率 (kW)
  E_k: 第k段末储能电量 (kWh)

目标: min Σ price_k * b_k * dt        （全天购电费）

约束:
  1) 供电满足负载:  b_k + pv_k + d_k - c_k >= load_k   （光伏过剩可弃光）
  2) 储能动态:      E_k = E_{k-1} + dt*(eta*c_k - d_k/eta)
  3) 电量上下限:    1200 <= E_k <= 10800
  4) 充放功率限制:  0 <= c_k, d_k <= 5000
  5) 边界条件:      E_0 = 6000, E_144 = 6000 （0:00与24:00电量相同）
"""
import numpy as np
import openpyxl
from scipy.optimize import linprog

# ---------------- 读取数据 ----------------
wb = openpyxl.load_workbook('附件/附件1.xlsx', data_only=True)
rows = list(wb['Sheet1'].iter_rows(min_row=2, values_only=True))
price = np.array([float(r[1]) for r in rows])   # 元/kWh
load  = np.array([float(r[2]) for r in rows])   # kW
pv    = np.array([float(r[3]) for r in rows])   # kW
n = len(price)
assert n == 144, n
print(f'数据: {n} 段 | 电价[{price.min():.4f},{price.max():.4f}] 元/kWh | '
      f'负载[{load.min():.0f},{load.max():.0f}] kW | 光伏最大 {pv.max():.0f} kW')

# ---------------- 参数（附录1） ----------------
dt   = 1/6      # h (10分钟)
eta  = 0.90     # 充放电效率
E0   = 6000.0   # 2025-01-01 0:00 初始电量
Emin, Emax = 1200.0, 10800.0
Pmax = 5000.0   # 最大充放电功率 kW

# ---------------- 构造LP ----------------
# z = [b(144), c(144), d(144), E(144)]
N = 4*n
obj = np.zeros(N)
obj[:n]      = price*dt     # 购电费
obj[n:2*n]   = 1e-9         # 极小惩罚项，破除“同时充放”退化，不影响最优值
obj[2*n:3*n] = 1e-9

A_ub = np.zeros((n, N)); b_ub = pv - load      # b + pv + d - c >= load
A_ub[:, :n]      = -np.eye(n)   # -b
A_ub[:, n:2*n]   =  np.eye(n)   # +c
A_ub[:, 2*n:3*n] = -np.eye(n)   # -d

A_eq = np.zeros((n+1, N)); b_eq = np.zeros(n+1)
for k in range(n):
    A_eq[k, 3*n+k] = 1.0                 # E_k
    if k > 0:
        A_eq[k, 3*n+k-1] = -1.0          # -E_{k-1}
    A_eq[k, n+k]   = -dt*eta             # -dt*eta*c_k
    A_eq[k, 2*n+k] =  dt/eta             # +dt/eta*d_k
b_eq[0] = E0                             # 第一段: E_1 - E_0(=6000) - ... = 0
A_eq[n, 4*n-1] = 1.0; b_eq[n] = E0       # E_144 = 6000

bounds = ([(0,None)]*n + [(0,Pmax)]*n + [(0,Pmax)]*n + [(Emin,Emax)]*n)

res = linprog(obj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
              bounds=bounds, method='highs')
print('求解状态:', res.status, '-', res.message)
assert res.status == 0
b, c, d, E = res.x[:n], res.x[n:2*n], res.x[2*n:3*n], res.x[3*n:]

# ---------------- 校验 ----------------
print('\n===== 约束校验 =====')
print('  负载约束最小裕度    = %.3e  (>=0 即满足)' % np.min(b + pv + d - c - load))
print('  储电量范围          = [%.2f, %.2f] kWh  (要求[1200,10800])' % (E.min(), E.max()))
print('  E_144 - 6000        = %.3e' % (E[-1]-E0))
print('  最大充/放功率        = %.2f / %.2f kW  (<=5000)' % (c.max(), d.max()))
print('  同时充放的段数       =', int(np.sum((c>1e-6)&(d>1e-6))))

buy_e, ch_e, dis_e = b*dt, c*dt, d*dt
cost_e = price*buy_e
print('\n===== 全天汇总 =====')
print('  全天购电量 = %.2f kWh' % buy_e.sum())
print('  全天购电费 = %.2f 元' % cost_e.sum())
print('  全天光伏发电 = %.2f kWh (自用或弃光)' % (pv*dt).sum())
print('  全天充电量 = %.2f kWh, 放电量 = %.2f kWh' % (ch_e.sum(), dis_e.sum()))

# ---------------- 逐小时明细（检查合理性） ----------------
def hm(m):
    h, mm = divmod(m, 60); return f'{h:02d}:{mm:02d}'
print('\n时段(结束)  电价    购电kWh  充电kWh  放电kWh   储电量kWh')
for k in range(n):
    if k % 6 == 5:  # 每小时打印一行（该小时合计）
        sl = slice(k-5, k+1)
        print('%s  %6.4f  %8.1f  %8.1f  %8.1f  %9.1f' % (
            hm((k+1)*10), price[k], buy_e[sl].sum(), ch_e[sl].sum(), dis_e[sl].sum(), E[k]))

# ---------------- 输出表1 / 表2 数据 ----------------
print('\n===== 表1: 指定10分钟时段购电量 =====')
for t_end in [610, 730, 850, 970, 1090, 1210]:  # 10:10,12:10,...,20:10 → 时段(10:00,10:10]...
    k = t_end//10 - 1
    print('  %s-%s : %10.2f kWh' % (hm(t_end-10), hm(t_end), buy_e[k]))
print('  全天购电量: %.2f kWh' % buy_e.sum())
print('  全天购电费: %.2f 元' % cost_e.sum())

print('\n===== 表2: 4小时时段充放电量 =====')
for i, (a, bb) in enumerate([(0,240),(240,480),(480,720),(720,960),(960,1200),(1200,1440)]):
    sl = slice(a//10, bb//10)
    print('  %s-%s : 充电 %10.2f kWh  放电 %10.2f kWh' % (
        hm(a), hm(bb) if bb<1440 else '24:00', ch_e[sl].sum(), dis_e[sl].sum()))
print('  0:00 储电量: %.2f kWh' % E0)
print('  24:00 储电量: %.2f kWh' % E[-1])

# ---------------- 保存中间结果供填表用 ----------------
np.savez('p1_solution.npz', price=price, load=load, pv=pv,
         b=b, c=c, d=d, E=E, buy_e=buy_e, ch_e=ch_e, dis_e=dis_e, cost_e=cost_e)
print('\n中间结果已保存至 p1_solution.npz')
