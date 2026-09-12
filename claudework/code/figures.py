# -*- coding: utf-8 -*-
"""生成论文用的矢量图，全部写进 figures/ 目录。"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from data_io import load_inputs, interval_labels, SOC_MIN, SOC_MAX, DISPLAY_DATES
from forecast import history_mean_forecast, pv_forecast_after, safety_margin, RELEASE_HOURS
from core import solve_plan, settle, roll_soc, emergency_runs
from p1 import solve_problem1
from p2 import run_problem2
from p3 import run_problem3
from p4 import run_problem4_2, run_problem4_3

FIG = Path(__file__).resolve().parents[1] / "figures"
FIG.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei"],
    "axes.unicode_minus": False,
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linewidth": 0.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})
C_PRICE, C_BUY, C_CHARGE, C_DISCHARGE, C_SOC = "#c0392b", "#2471a3", "#1e8449", "#d68910", "#6c3483"
HOURS = np.arange(144) / 6.0


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, bbox_inches="tight")
    plt.close(fig)
    print("  写出", name)


def fig_problem1(ins, dispatch):
    """问题1：电价与购电量、充放电、储电量。"""
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 6.6), sharex=True,
                             gridspec_kw=dict(height_ratios=[1.15, 0.75, 1.0], hspace=0.18))
    ax = axes[0]
    ax.step(HOURS, ins.a1_price, where="post", color=C_PRICE, lw=1.4, zorder=5)
    ax.fill_between(HOURS, 0, ins.a1_price, step="post", color=C_PRICE, alpha=0.10, zorder=1)
    ax.set_ylabel("电价 (元/kWh)", color=C_PRICE, fontsize=8.5)
    ax.tick_params(axis="y", labelcolor=C_PRICE, labelsize=8)
    ax.set_ylim(0, 1.55)
    twin = ax.twinx()
    twin.bar(HOURS, dispatch.purchase, width=1 / 6, color=C_BUY, alpha=0.6, zorder=2)
    twin.set_ylabel("计划购电量 (kWh/10min)", color=C_BUY, fontsize=8.5)
    twin.tick_params(axis="y", labelcolor=C_BUY, labelsize=8)
    twin.set_ylim(0, 2100)
    twin.grid(False)
    ax.set_title("问题1 典型日：电价、购电量与储能调度", fontsize=10)

    ax = axes[1]
    ax.bar(HOURS, dispatch.charge, width=1 / 6, color=C_CHARGE, label="充电量")
    ax.bar(HOURS, -dispatch.discharge, width=1 / 6, color=C_DISCHARGE, label="放电量")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_ylabel("充放电量 (kWh)", fontsize=8.5)
    ax.tick_params(labelsize=8)
    ax.legend(loc="upper left", ncol=2, frameon=False, fontsize=8)

    ax = axes[2]
    ax.plot(HOURS, dispatch.soc, color=C_SOC, lw=1.5)
    ax.axhline(SOC_MAX, color="gray", ls="--", lw=0.8, label="上限 10800")
    ax.axhline(SOC_MIN, color="gray", ls=":", lw=0.8, label="下限 1200")
    ax.axhline(6000, color="black", ls="-.", lw=0.8, label="初始 6000")
    ax.set_ylabel("储电量 (kWh)", fontsize=8.5)
    ax.set_xlabel("时刻 (h)")
    ax.set_ylim(0, 12000)
    ax.set_xticks(range(0, 25, 3))
    ax.tick_params(labelsize=8)
    ax.legend(loc="upper left", ncol=3, frameon=False, fontsize=8)
    save(fig, "p1_dispatch.pdf")


def fig_margin(ins):
    """安全裕度分位点对费用的影响，标出理论最优 0.8。"""
    quantiles = np.arange(0.30, 0.96, 0.05)
    plan, emg, total = [], [], []
    for q in quantiles:
        p_sum = e_sum = 0.0
        soc = 6000.0
        for day in range(365):
            fc_load = history_mean_forecast(ins.load, day)
            fc_pv = history_mean_forecast(ins.pv, day)
            d = solve_plan(fc_load, fc_pv, ins.a1_price, soc_start=soc, soc_end=soc)
            lo = max(1, day - 28)
            if lo < day:
                errors = np.array([
                    (ins.load[t] - history_mean_forecast(ins.load, t))
                    - (ins.pv[t] - history_mean_forecast(ins.pv, t)) for t in range(lo, day)])
                margin = np.maximum(np.quantile(errors, q, axis=0), 0.0)
            else:
                margin = np.zeros(144)
            buy = d.purchase + margin
            r = settle(ins.load[day], ins.pv[day], ins.a1_price, buy, d.charge, d.discharge)
            if day >= 31:
                p_sum += float((buy * ins.a1_price).sum())
                e_sum += r.emergency_cost
            soc = d.soc[-1]
        plan.append(p_sum / 1e4)
        emg.append(e_sum / 1e4)
        total.append((p_sum + e_sum) / 1e4)

    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ax.plot(quantiles, plan, "o-", ms=3, color=C_BUY, label="计划购电费")
    ax.plot(quantiles, emg, "s-", ms=3, color=C_PRICE, label="紧急购电费")
    ax.plot(quantiles, total, "^-", ms=4, color=C_SOC, lw=1.8, label="总费用")
    best = int(np.argmin(total))
    ax.axvline(quantiles[best], color="gray", ls="--", lw=0.9)
    ax.annotate(f"最优 {quantiles[best]:.2f}\n{total[best]:.0f} 万元",
                xy=(quantiles[best], total[best]), xytext=(quantiles[best] + 0.03, total[best] + 130),
                fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.8, color="gray"))
    ax.set_xlabel("安全裕度分位点 $q$")
    ax.set_ylabel("全年费用 (万元)")
    ax.legend(frameon=False)
    ax.set_title("安全裕度取误差分布的 $q$ 分位点时的问题2 全年费用", fontsize=10)
    save(fig, "margin_tradeoff.pdf")
    return quantiles, total


def fig_monthly(ins, rec2, rec3):
    """问题2、问题3 的逐月费用构成与紧急购电量对比。"""
    months = np.array([d.astype("datetime64[M]").astype(int) % 12 + 1 for d in ins.dates[31:]])
    labels = [f"{m}月" for m in range(2, 13)]
    p2 = np.array([r["plan_cost"] for r in rec2[31:]])
    e2 = np.array([r["real"].emergency_cost for r in rec2[31:]])
    t3 = np.array([r["real"].total_cost for r in rec3[31:]])
    k2 = np.array([r["real"].emergency.sum() for r in rec2[31:]])
    k3 = np.array([r["real"].emergency.sum() for r in rec3[31:]])

    def by_month(values):
        return np.array([values[months == m].sum() for m in range(2, 13)])

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.1))
    ax = axes[0]
    x = np.arange(len(labels))
    ax.bar(x - 0.2, by_month(p2) / 1e4, 0.4, color=C_BUY, label="问题2 计划购电费")
    ax.bar(x - 0.2, by_month(e2) / 1e4, 0.4, bottom=by_month(p2) / 1e4, color=C_PRICE, label="问题2 紧急购电费")
    ax.bar(x + 0.2, by_month(t3) / 1e4, 0.4, color=C_SOC, alpha=0.85, label="问题3 总费用")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("费用 (万元)")
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("逐月费用构成", fontsize=10)

    ax = axes[1]
    ax.bar(x - 0.2, by_month(k2) / 1e3, 0.4, color=C_PRICE, label="问题2")
    ax.bar(x + 0.2, by_month(k3) / 1e3, 0.4, color=C_SOC, alpha=0.85, label="问题3 滚动")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("紧急购电量 (MWh)")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("逐月紧急购电量", fontsize=10)
    save(fig, "p2p3_monthly.pdf")


def fig_forecast(ins):
    """光伏预测精度的公平对比：同一时段、同一误差口径。"""
    segs = [(0, 36), (36, 72), (72, 108), (108, 144)]

    def mae(pred_fn, lo, hi):
        err = np.concatenate([pred_fn(d)[lo:hi] - ins.pv[d, lo:hi] for d in range(31, 365)])
        return np.abs(err).mean()

    only0, rolling, mean7 = [], [], []
    for (lo, hi), hour in zip(segs, RELEASE_HOURS):
        only0.append(mae(lambda d: pv_forecast_after(ins, d, 0), lo, hi))
        rolling.append(mae(lambda d: np.r_[np.zeros(lo), pv_forecast_after(ins, d, hour)], lo, hi))
        mean7.append(mae(lambda d: history_mean_forecast(ins.pv, d), lo, hi))

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    x = np.arange(len(segs))
    names = [f"{lo // 6}:00-{hi // 6}:00" for lo, hi in segs]
    ax.bar(x - 0.26, mean7, 0.26, color="#95a5a6", label="前7日均值")
    ax.bar(x, only0, 0.26, color="#5dade2", label="只用 0:00 预报")
    ax.bar(x + 0.26, rolling, 0.26, color=C_BUY, label="滚动使用最新预报")
    for i, (a, b, c) in enumerate(zip(mean7, only0, rolling)):
        ax.text(i - 0.26, a + 4, f"{a:.0f}", ha="center", fontsize=7)
        ax.text(i, b + 4, f"{b:.0f}", ha="center", fontsize=7)
        ax.text(i + 0.26, c + 4, f"{c:.0f}", ha="center", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=8)
    ax.set_xlabel("时段"); ax.set_ylabel("光伏预测 MAE (kWh/10min)")
    ax.set_ylim(0, max(only0) * 1.25)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("同一时段下三种光伏预测的误差对比", fontsize=10)
    save(fig, "forecast_accuracy.pdf")


def fig_problem4(ins, rec2, rec42, rec43):
    """波动电价的特征与两种电价下的费用对比。"""
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.1))
    ax = axes[0]
    ax.plot(HOURS, ins.a1_price, color=C_PRICE, lw=1.3, label="附件1 固定日内电价")
    day = int(np.where(ins.dates == np.datetime64("2025-07-15"))[0][0])
    ax.plot(HOURS, ins.price[day], color=C_BUY, lw=1.0, alpha=0.85, label="附件4 实时电价（7-15）")
    ax.plot(HOURS, history_mean_forecast(ins.price, day), color=C_SOC, lw=1.1, ls="--",
            label="实时电价的 7 日均值预测")
    ax.set_xlabel("时刻 (h)"); ax.set_ylabel("电价 (元/kWh)")
    ax.set_xticks(range(0, 25, 4))
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("固定电价与波动电价", fontsize=10)

    ax = axes[1]
    months = np.array([d.astype("datetime64[M]").astype(int) % 12 + 1 for d in ins.dates[31:]])

    def by_month(values):
        return np.array([values[months == m].sum() for m in range(2, 13)]) / 1e4

    x = np.arange(11)
    labels = [f"{m}月" for m in range(2, 13)]
    ax.bar(x - 0.25, by_month(np.array([r["plan_cost"] + r["real"].emergency_cost for r in rec2[31:]])),
           0.25, color=C_BUY, label="问题2 固定电价")
    ax.bar(x, by_month(np.array([r["plan_cost"] + r["real"].emergency_cost for r in rec42[31:]])),
           0.25, color=C_PRICE, label="问题4-2 波动电价")
    ax.bar(x + 0.25, by_month(np.array([r["real"].total_cost for r in rec43[31:]])),
           0.25, color=C_SOC, alpha=0.85, label="问题4-3 波动电价")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("费用 (万元)")
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("逐月费用对比", fontsize=10)
    save(fig, "p4_price.pdf")


def fig_display_days(ins, rec2, rec3):
    """四个指定日期的调度：购电量与储电量。"""
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 5.0))
    for ax, date in zip(axes.ravel(), DISPLAY_DATES):
        r2 = next(r for r in rec2[31:] if str(ins.dates[r["day"]]) == date)
        r3 = next(r for r in rec3[31:] if str(ins.dates[r["day"]]) == date)
        buy2 = r2["purchase"] + r2["real"].emergency
        buy3 = r3["purchase"] + r3["real"].emergency
        ax.fill_between(HOURS, 0, buy2, step="post", color=C_BUY, alpha=0.30,
                        label="问题2 购电")
        ax.step(HOURS, buy3, where="post", color=C_PRICE, lw=1.2,
                label="问题3 调整后购电")
        twin = ax.twinx()
        twin.plot(HOURS, r3["soc_track"], color=C_SOC, lw=1.3, label="问题3 储电量")
        twin.axhline(6000, color="gray", ls=":", lw=0.7)
        twin.set_ylim(0, 12000)
        twin.grid(False)
        ax.set_title(date, fontsize=9.5)
        ax.set_ylabel("购电量 (kWh)", fontsize=8)
        twin.set_ylabel("储电量 (kWh)", fontsize=8, color=C_SOC)
        ax.set_xticks(range(0, 25, 6))
        ax.tick_params(labelsize=7.5)
        twin.tick_params(labelsize=7.5, labelcolor=C_SOC)
        if date == DISPLAY_DATES[0]:
            ax.legend(loc="upper left", frameon=False, fontsize=7)
            twin.legend(loc="upper right", frameon=False, fontsize=7)
    for ax in axes[1]:
        ax.set_xlabel("时刻 (h)", fontsize=8)
    save(fig, "display_days.pdf")


def main():
    ins = load_inputs()
    print("生成图表：")
    _, dispatch1 = solve_problem1()
    fig_problem1(ins, dispatch1)
    fig_margin(ins)
    rec2 = run_problem2(ins)
    rec3 = run_problem3(ins)
    fig_monthly(ins, rec2, rec3)
    fig_forecast(ins)
    rec42 = run_problem4_2(ins)
    rec43 = run_problem4_3(ins)
    fig_problem4(ins, rec2, rec42, rec43)
    fig_display_days(ins, rec2, rec3)


if __name__ == "__main__":
    main()
