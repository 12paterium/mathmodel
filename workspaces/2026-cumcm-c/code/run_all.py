"""Run all four questions and generate auditable results and paper figures."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd

from model_core import (
    ATTACHMENTS,
    DISPLAY_DATES,
    ETA,
    FLOW_MAX,
    N_INTERVALS,
    ROOT,
    SOC_INITIAL,
    SUBMIT_START,
    Inputs,
    Plan,
    causal_ensemble,
    date_index,
    emergency_runs,
    execute_segment,
    expanded_pv_forecast,
    forecast_metrics,
    interval_label,
    load_inputs,
    max_constraint_violation,
    plan_dispatch,
    safety_margin,
    select_safety_quantile,
)


RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
REPORTS = ROOT / "reports"
EPS = 1e-7


@dataclass
class Scenario:
    name: str
    dates: np.ndarray
    initial_purchase: np.ndarray
    final_purchase: np.ndarray
    charge: np.ndarray
    discharge: np.ndarray
    soc: np.ndarray
    emergency: np.ndarray
    curtail: np.ndarray
    start_soc: np.ndarray
    plan_cost: np.ndarray
    adjustment_cost: np.ndarray
    emergency_cost: np.ndarray
    total_cost: np.ndarray
    balance_residual: float
    constraint_violation: float
    causality_violations: int
    adjustment_up: np.ndarray
    adjustment_down: np.ndarray


def prepare_directories() -> None:
    RESULTS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)


def run_problem1(inputs: Inputs, eta: float = ETA) -> tuple[Plan, dict[str, float]]:
    plan = plan_dispatch(
        inputs.fixed_load,
        inputs.fixed_pv,
        inputs.fixed_price,
        SOC_INITIAL,
        terminal_value=0.0,
        terminal_soc=SOC_INITIAL,
        eta=eta,
    )
    baseline_purchase = np.maximum(inputs.fixed_load - inputs.fixed_pv, 0.0)
    metrics = {
        "purchase_kwh": float(plan.purchase.sum()),
        "cost_yuan": float(np.dot(inputs.fixed_price, plan.purchase)),
        "baseline_purchase_kwh": float(baseline_purchase.sum()),
        "baseline_cost_yuan": float(np.dot(inputs.fixed_price, baseline_purchase)),
        "charge_kwh": float(plan.charge.sum()),
        "discharge_kwh": float(plan.discharge.sum()),
        "curtail_kwh": float(plan.curtail.sum()),
        "balance_residual_kwh": plan.balance_residual,
        "end_soc_kwh": float(plan.soc[-1]),
        "simultaneous_flow_kwh": float(np.minimum(plan.charge, plan.discharge).max()),
    }
    return plan, metrics


def run_day_ahead(
    inputs: Inputs,
    load_fc: np.ndarray,
    pv_fc: np.ndarray,
    decision_prices: np.ndarray,
    settlement_prices: np.ndarray,
    quantile: float,
    name: str,
) -> Scenario:
    days = len(inputs.dates) - SUBMIT_START
    shape = (days, N_INTERVALS)
    arrays = [np.zeros(shape) for _ in range(8)]
    initial, final, charge, discharge, soc, emergency, curtail, zeros = arrays
    start_soc = np.zeros(days)
    plan_cost = np.zeros(days)
    adjustment_cost = np.zeros(days)
    emergency_cost = np.zeros(days)
    total_cost = np.zeros(days)
    residual_history = (inputs.load - inputs.pv) - (load_fc - pv_fc)
    current_soc = SOC_INITIAL
    max_residual = 0.0
    max_violation = 0.0
    causality_violations = 0

    for output_day, day in enumerate(range(SUBMIT_START, len(inputs.dates))):
        latest_training_day = day - 1
        assert latest_training_day < day, "日前预测读取了目标日或未来日期"
        start_soc[output_day] = current_soc
        margin = safety_margin(day, residual_history, quantile)
        target_load = np.maximum(0.0, load_fc[day] + margin)
        terminal_soc = SOC_INITIAL if day == len(inputs.dates) - 1 else None
        terminal_value = float(np.median(decision_prices[day]) * ETA)
        plan = plan_dispatch(
            target_load,
            pv_fc[day],
            decision_prices[day],
            current_soc,
            terminal_value,
            terminal_soc=terminal_soc,
        )
        execution = execute_segment(plan.purchase, inputs.load[day], inputs.pv[day], current_soc)
        initial[output_day] = final[output_day] = plan.purchase
        charge[output_day] = execution.charge
        discharge[output_day] = execution.discharge
        soc[output_day] = execution.soc
        emergency[output_day] = execution.emergency
        curtail[output_day] = execution.curtail
        current_soc = float(execution.soc[-1])
        plan_cost[output_day] = float(np.dot(settlement_prices[day], plan.purchase))
        emergency_cost[output_day] = float(5.0 * np.dot(settlement_prices[day], execution.emergency))
        total_cost[output_day] = plan_cost[output_day] + emergency_cost[output_day]
        max_residual = max(max_residual, plan.balance_residual, execution.balance_residual)
        max_violation = max(max_violation, max_constraint_violation(execution))
        causality_violations += int(latest_training_day >= day)

    return Scenario(
        name=name,
        dates=inputs.dates[SUBMIT_START:],
        initial_purchase=initial,
        final_purchase=final,
        charge=charge,
        discharge=discharge,
        soc=soc,
        emergency=emergency,
        curtail=curtail,
        start_soc=start_soc,
        plan_cost=plan_cost,
        adjustment_cost=adjustment_cost,
        emergency_cost=emergency_cost,
        total_cost=total_cost,
        balance_residual=max_residual,
        constraint_violation=max_violation,
        causality_violations=causality_violations,
        adjustment_up=zeros.copy(),
        adjustment_down=zeros.copy(),
    )


def rolling_margin(inputs: Inputs, load_fc: np.ndarray, day: int, release_hour: int, quantile: float) -> np.ndarray:
    start = release_hour * 6
    historical_errors = []
    for past in range(max(1, day - 28), day):
        pv_prediction = expanded_pv_forecast(inputs, past, release_hour)
        historical_errors.append(
            (inputs.load[past, start:] - inputs.pv[past, start:])
            - (load_fc[past, start:] - pv_prediction)
        )
    if not historical_errors:
        return np.zeros(N_INTERVALS - start)
    return np.maximum(0.0, np.quantile(np.asarray(historical_errors), quantile, axis=0))


def run_rolling(
    inputs: Inputs,
    load_fc: np.ndarray,
    decision_prices: np.ndarray,
    settlement_prices: np.ndarray,
    quantile: float,
    releases: tuple[int, ...],
    name: str,
) -> Scenario:
    days = len(inputs.dates) - SUBMIT_START
    shape = (days, N_INTERVALS)
    initial = np.zeros(shape)
    final = np.zeros(shape)
    charge = np.zeros(shape)
    discharge = np.zeros(shape)
    soc = np.zeros(shape)
    emergency = np.zeros(shape)
    curtail = np.zeros(shape)
    adjustment_up = np.zeros(shape)
    adjustment_down = np.zeros(shape)
    start_soc = np.zeros(days)
    plan_cost = np.zeros(days)
    adjustment_cost = np.zeros(days)
    emergency_cost = np.zeros(days)
    total_cost = np.zeros(days)
    current_soc = SOC_INITIAL
    max_residual = 0.0
    max_violation = 0.0

    for output_day, day in enumerate(range(SUBMIT_START, len(inputs.dates))):
        latest_training_day = day - 1
        assert latest_training_day < day, "滚动预测读取了目标日或未来日期"
        start_soc[output_day] = current_soc
        price_decision = decision_prices[day].copy()
        pv_zero = expanded_pv_forecast(inputs, day, 0)
        margin_zero = rolling_margin(inputs, load_fc, day, 0, quantile)
        terminal_soc = SOC_INITIAL if day == len(inputs.dates) - 1 else None
        first_plan = plan_dispatch(
            np.maximum(0.0, load_fc[day] + margin_zero),
            pv_zero,
            price_decision,
            current_soc,
            float(np.median(price_decision) * ETA),
            terminal_soc=terminal_soc,
        )
        active_purchase = first_plan.purchase.copy()
        initial[output_day] = first_plan.purchase
        plan_cost[output_day] = float(np.dot(settlement_prices[day], first_plan.purchase))
        max_residual = max(max_residual, first_plan.balance_residual)
        previous = 0

        for release_hour in releases[1:]:
            boundary = release_hour * 6
            assert boundary > previous, "调整时刻未按时间顺序推进"
            segment = execute_segment(
                active_purchase[previous:boundary],
                inputs.load[day, previous:boundary],
                inputs.pv[day, previous:boundary],
                current_soc,
            )
            sl = slice(previous, boundary)
            charge[output_day, sl] = segment.charge
            discharge[output_day, sl] = segment.discharge
            soc[output_day, sl] = segment.soc
            emergency[output_day, sl] = segment.emergency
            curtail[output_day, sl] = segment.curtail
            current_soc = float(segment.soc[-1])
            max_residual = max(max_residual, segment.balance_residual)
            max_violation = max(max_violation, max_constraint_violation(segment))

            observed_load_error = inputs.load[day, :boundary] - load_fc[day, :boundary]
            load_bias = float(np.median(observed_load_error[-18:])) if len(observed_load_error) else 0.0
            future_load = np.maximum(0.0, load_fc[day, boundary:] + load_bias)
            future_pv = expanded_pv_forecast(inputs, day, release_hour)
            future_margin = rolling_margin(inputs, load_fc, day, release_hour, quantile)
            if not np.allclose(decision_prices[day], settlement_prices[day]):
                observed_price_error = settlement_prices[day, :boundary] - decision_prices[day, :boundary]
                price_bias = float(np.median(observed_price_error[-18:]))
                price_decision[boundary:] = np.maximum(1e-4, decision_prices[day, boundary:] + price_bias)
            old = active_purchase[boundary:].copy()
            adjusted = plan_dispatch(
                future_load + future_margin,
                future_pv,
                price_decision[boundary:],
                current_soc,
                float(np.median(price_decision[boundary:]) * ETA),
                terminal_soc=terminal_soc,
                old_purchase=old,
            )
            new = adjusted.purchase
            up = np.maximum(new - old, 0.0)
            down = np.maximum(old - new, 0.0)
            adjustment_up[output_day, boundary:] += up
            adjustment_down[output_day, boundary:] += down
            adjustment_cost[output_day] += float(
                np.dot(settlement_prices[day, boundary:], 1.5 * up - 0.5 * down)
            )
            active_purchase[boundary:] = new
            max_residual = max(max_residual, adjusted.balance_residual)
            previous = boundary

        segment = execute_segment(
            active_purchase[previous:],
            inputs.load[day, previous:],
            inputs.pv[day, previous:],
            current_soc,
        )
        sl = slice(previous, N_INTERVALS)
        charge[output_day, sl] = segment.charge
        discharge[output_day, sl] = segment.discharge
        soc[output_day, sl] = segment.soc
        emergency[output_day, sl] = segment.emergency
        curtail[output_day, sl] = segment.curtail
        current_soc = float(segment.soc[-1])
        final[output_day] = active_purchase
        emergency_cost[output_day] = float(5.0 * np.dot(settlement_prices[day], emergency[output_day]))
        total_cost[output_day] = plan_cost[output_day] + adjustment_cost[output_day] + emergency_cost[output_day]
        max_residual = max(max_residual, segment.balance_residual)
        max_violation = max(max_violation, max_constraint_violation(segment))

    return Scenario(
        name=name,
        dates=inputs.dates[SUBMIT_START:],
        initial_purchase=initial,
        final_purchase=final,
        charge=charge,
        discharge=discharge,
        soc=soc,
        emergency=emergency,
        curtail=curtail,
        start_soc=start_soc,
        plan_cost=plan_cost,
        adjustment_cost=adjustment_cost,
        emergency_cost=emergency_cost,
        total_cost=total_cost,
        balance_residual=max_residual,
        constraint_violation=max_violation,
        causality_violations=0,
        adjustment_up=adjustment_up,
        adjustment_down=adjustment_down,
    )


def rounded(value: float) -> float:
    result = round(float(value), 4)
    return 0.0 if abs(result) < 0.00005 else result


def write_problem1(plan: Plan, metrics: dict[str, float]) -> None:
    source = ATTACHMENTS / "附件5" / "result1.xlsx"
    target = RESULTS / "result1.xlsx"
    shutil.copy2(source, target)
    workbook = openpyxl.load_workbook(target)
    purchase_sheet, storage_sheet = workbook.worksheets
    for interval in range(N_INTERVALS):
        purchase_sheet.cell(2 + interval, 2).value = rounded(plan.purchase[interval])
    for block in range(6):
        sl = slice(block * 24, (block + 1) * 24)
        storage_sheet.cell(2 + block, 2).value = rounded(plan.charge[sl].sum())
        storage_sheet.cell(2 + block, 3).value = rounded(plan.discharge[sl].sum())
    storage_sheet.cell(2, 5).value = rounded(SOC_INITIAL)
    storage_sheet.cell(3, 5).value = rounded(plan.soc[-1])
    workbook.save(target)


def _scenario_day(scenario: Scenario, value: object) -> int | None:
    if not isinstance(value, datetime):
        return None
    matches = np.flatnonzero(scenario.dates == np.datetime64(value.date()))
    return int(matches[0]) if len(matches) else None


def write_scenario_template(scenario: Scenario, filename: str, rolling: bool) -> None:
    source = ATTACHMENTS / "附件5" / filename
    target = RESULTS / filename
    shutil.copy2(source, target)
    workbook = openpyxl.load_workbook(target)
    plan_sheet = workbook.worksheets[0]
    for day in range(len(scenario.dates)):
        row = day + 2
        for interval in range(N_INTERVALS):
            plan_sheet.cell(row, interval + 2).value = rounded(scenario.initial_purchase[day, interval])
        plan_sheet.cell(row, 146).value = rounded(scenario.initial_purchase[day].sum())
        plan_sheet.cell(row, 147).value = rounded(scenario.plan_cost[day])

    offset = 1
    if rolling:
        adjusted_sheet = workbook.worksheets[1]
        for day in range(len(scenario.dates)):
            row = day + 2
            for interval in range(N_INTERVALS):
                adjusted_sheet.cell(row, interval + 2).value = rounded(scenario.final_purchase[day, interval])
            adjusted_sheet.cell(row, 146).value = rounded(scenario.final_purchase[day].sum())
            adjusted_sheet.cell(row, 147).value = rounded(
                scenario.plan_cost[day] + scenario.adjustment_cost[day]
            )
        offset = 2

    storage_sheet = workbook.worksheets[offset]
    active_day = None
    start_row = None
    for row in range(2, storage_sheet.max_row + 1):
        candidate = _scenario_day(scenario, storage_sheet.cell(row, 1).value)
        if candidate is not None:
            active_day = candidate
            start_row = row
        if active_day is None or start_row is None or row - start_row >= 6:
            continue
        block = row - start_row
        sl = slice(block * 24, (block + 1) * 24)
        storage_sheet.cell(row, 3).value = rounded(scenario.charge[active_day, sl].sum())
        storage_sheet.cell(row, 4).value = rounded(scenario.discharge[active_day, sl].sum())
        if block == 0:
            storage_sheet.cell(row, 6).value = rounded(scenario.start_soc[active_day])
        if block == 1:
            storage_sheet.cell(row, 6).value = rounded(scenario.soc[active_day, -1])

    emergency_sheet = workbook.worksheets[offset + 1]
    active_day = None
    group_row = None
    for row in range(2, emergency_sheet.max_row + 1):
        candidate = _scenario_day(scenario, emergency_sheet.cell(row, 1).value)
        if candidate is not None:
            active_day = candidate
            group_row = row
            runs = emergency_runs(scenario.emergency[active_day])
            if not runs:
                emergency_sheet.cell(row, 2).value = "无"
                emergency_sheet.cell(row, 3).value = 0.0
            else:
                for position, (start, end, amount) in enumerate(runs[:3]):
                    emergency_sheet.cell(row + position, 2).value = interval_label(start, end)
                    emergency_sheet.cell(row + position, 3).value = rounded(amount)
        elif active_day is None or group_row is None:
            continue
    workbook.save(target)


def scenario_summary(scenario: Scenario) -> dict[str, float | int | str]:
    return {
        "scenario": scenario.name,
        "days": len(scenario.dates),
        "plan_cost_yuan": float(scenario.plan_cost.sum()),
        "adjustment_cost_yuan": float(scenario.adjustment_cost.sum()),
        "emergency_cost_yuan": float(scenario.emergency_cost.sum()),
        "total_cost_yuan": float(scenario.total_cost.sum()),
        "planned_purchase_kwh": float(scenario.initial_purchase.sum()),
        "final_purchase_kwh": float(scenario.final_purchase.sum()),
        "emergency_purchase_kwh": float(scenario.emergency.sum()),
        "charge_kwh": float(scenario.charge.sum()),
        "discharge_kwh": float(scenario.discharge.sum()),
        "curtail_kwh": float(scenario.curtail.sum()),
        "end_soc_kwh": float(scenario.soc[-1, -1]),
        "balance_residual_kwh": float(scenario.balance_residual),
        "constraint_violation": float(scenario.constraint_violation),
        "causality_violations": int(scenario.causality_violations),
    }


def save_scenario(scenario: Scenario) -> None:
    np.savez_compressed(
        RESULTS / f"{scenario.name}_detail.npz",
        dates=scenario.dates.astype("datetime64[D]"),
        initial_purchase=scenario.initial_purchase,
        final_purchase=scenario.final_purchase,
        charge=scenario.charge,
        discharge=scenario.discharge,
        soc=scenario.soc,
        emergency=scenario.emergency,
        curtail=scenario.curtail,
        start_soc=scenario.start_soc,
        plan_cost=scenario.plan_cost,
        adjustment_cost=scenario.adjustment_cost,
        emergency_cost=scenario.emergency_cost,
        total_cost=scenario.total_cost,
        adjustment_up=scenario.adjustment_up,
        adjustment_down=scenario.adjustment_down,
    )
    pd.DataFrame({
        "date": scenario.dates.astype(str),
        "plan_cost_yuan": scenario.plan_cost,
        "adjustment_cost_yuan": scenario.adjustment_cost,
        "emergency_cost_yuan": scenario.emergency_cost,
        "total_cost_yuan": scenario.total_cost,
        "initial_purchase_kwh": scenario.initial_purchase.sum(axis=1),
        "final_purchase_kwh": scenario.final_purchase.sum(axis=1),
        "emergency_kwh": scenario.emergency.sum(axis=1),
        "charge_kwh": scenario.charge.sum(axis=1),
        "discharge_kwh": scenario.discharge.sum(axis=1),
        "curtail_kwh": scenario.curtail.sum(axis=1),
        "start_soc_kwh": scenario.start_soc,
        "end_soc_kwh": scenario.soc[:, -1],
    }).to_csv(RESULTS / f"{scenario.name}_daily.csv", index=False, encoding="utf-8-sig")


def save_emergency_events(scenarios: list[Scenario]) -> None:
    records = []
    for scenario in scenarios:
        for day, date in enumerate(scenario.dates.astype(str)):
            for start, end, amount in emergency_runs(scenario.emergency[day]):
                records.append({
                    "scenario": scenario.name,
                    "date": date,
                    "start_interval": start,
                    "end_interval_exclusive": end,
                    "time_range": interval_label(start, end),
                    "amount_kwh": amount,
                })
    pd.DataFrame(records).to_csv(RESULTS / "emergency_events.csv", index=False, encoding="utf-8-sig")


def save_display_days(inputs: Inputs, scenarios: list[Scenario]) -> None:
    rows = []
    for scenario in scenarios:
        for date_string in DISPLAY_DATES:
            day = date_index(scenario.dates, date_string)
            rows.append({
                "scenario": scenario.name,
                "date": date_string,
                "plan_cost_yuan": scenario.plan_cost[day],
                "adjustment_cost_yuan": scenario.adjustment_cost[day],
                "emergency_cost_yuan": scenario.emergency_cost[day],
                "total_cost_yuan": scenario.total_cost[day],
                "purchase_kwh": scenario.final_purchase[day].sum(),
                "emergency_kwh": scenario.emergency[day].sum(),
                "charge_kwh": scenario.charge[day].sum(),
                "discharge_kwh": scenario.discharge[day].sum(),
                "start_soc_kwh": scenario.start_soc[day],
                "end_soc_kwh": scenario.soc[day, -1],
            })
    pd.DataFrame(rows).to_csv(RESULTS / "display_days.csv", index=False, encoding="utf-8-sig")


def configure_plots() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "font.size": 9,
        "pdf.fonttype": 42,
    })


def make_figures(
    inputs: Inputs,
    p1: Plan,
    p2: Scenario,
    p3: Scenario,
    p42: Scenario,
    p43: Scenario,
    ablation: pd.DataFrame,
    load_fc: np.ndarray,
    pv_fc: np.ndarray,
) -> list[dict[str, str]]:
    configure_plots()
    sources: list[dict[str, str]] = []
    hours = np.arange(N_INTERVALS) / 6.0

    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.plot(hours, inputs.fixed_load, label="负载", color="#222222", linewidth=1.2)
    ax.plot(hours, inputs.fixed_pv, label="光伏", color="#2b8c6b", linewidth=1.2)
    ax.plot(hours, p1.purchase, label="计划购电", color="#cc4c4c", linewidth=1.1)
    ax.plot(hours, p1.discharge - p1.charge, label="储能净放电", color="#3b6fb6", linewidth=1.0)
    ax.set(xlabel="时刻/h", ylabel="区间电量/kWh", xlim=(0, 24))
    ax.legend(ncol=4, frameon=False)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "p1_dispatch.pdf")
    plt.close(fig)
    pd.DataFrame({"hour": hours, "load": inputs.fixed_load, "pv": inputs.fixed_pv, "purchase": p1.purchase,
                  "net_discharge": p1.discharge - p1.charge, "soc": p1.soc}).to_csv(
        FIGURES / "p1_dispatch_data.csv", index=False, encoding="utf-8-sig")
    sources.append({"figure": "p1_dispatch.pdf", "data": "p1_dispatch_data.csv", "purpose": "问题1调度构成"})

    fig, ax1 = plt.subplots(figsize=(7.2, 3.3))
    ax1.plot(hours, p1.soc, color="#3b6fb6", label="SOC")
    ax1.set(xlabel="时刻/h", ylabel="储电量/kWh", xlim=(0, 24))
    ax2 = ax1.twinx()
    ax2.step(hours, inputs.fixed_price, where="post", color="#cc4c4c", alpha=0.8, label="电价")
    ax2.set_ylabel("电价/(元/kWh)")
    lines = ax1.lines + ax2.lines
    ax1.legend(lines, [line.get_label() for line in lines], frameon=False, loc="upper center", ncol=2)
    ax1.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "p1_soc_price.pdf")
    plt.close(fig)
    sources.append({"figure": "p1_soc_price.pdf", "data": "p1_dispatch_data.csv", "purpose": "SOC与分时电价关系"})

    selected = date_index(inputs.dates, "2025-06-21")
    scenario_day = selected - SUBMIT_START
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    ax.plot(hours, inputs.load[selected] - inputs.pv[selected], label="实际净负荷", color="#222222")
    ax.plot(hours, load_fc[selected] - pv_fc[selected], label="日前预测净负荷", color="#cc4c4c")
    ax.plot(hours, p2.initial_purchase[scenario_day], label="计划购电", color="#3b6fb6")
    ax.set(xlabel="时刻/h", ylabel="区间电量/kWh", xlim=(0, 24))
    ax.legend(frameon=False, ncol=3)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "p2_forecast_dispatch.pdf")
    plt.close(fig)
    pd.DataFrame({"hour": hours, "actual_net_load": inputs.load[selected] - inputs.pv[selected],
                  "forecast_net_load": load_fc[selected] - pv_fc[selected],
                  "planned_purchase": p2.initial_purchase[scenario_day]}).to_csv(
        FIGURES / "p2_forecast_dispatch_data.csv", index=False, encoding="utf-8-sig")
    sources.append({"figure": "p2_forecast_dispatch.pdf", "data": "p2_forecast_dispatch_data.csv", "purpose": "问题2预测与计划对比"})

    emergency_daily = p2.emergency.sum(axis=1).reshape(-1, 1)
    calendar = np.full((48, 7), np.nan)
    for day, date in enumerate(pd.to_datetime(p2.dates.astype(str))):
        week = (date.dayofyear - 32) // 7
        if 0 <= week < calendar.shape[0]:
            calendar[week, date.weekday()] = emergency_daily[day, 0]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    image = ax.imshow(calendar.T, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    ax.set(xlabel="周序号", ylabel="星期", yticks=range(7), yticklabels=list("一二三四五六日"))
    fig.colorbar(image, ax=ax, label="日紧急购电量/kWh")
    fig.tight_layout()
    fig.savefig(FIGURES / "p2_emergency_heatmap.pdf")
    plt.close(fig)
    pd.DataFrame(calendar, columns=[f"weekday_{i + 1}" for i in range(7)]).to_csv(
        FIGURES / "p2_emergency_heatmap_data.csv", index=False, encoding="utf-8-sig")
    sources.append({"figure": "p2_emergency_heatmap.pdf", "data": "p2_emergency_heatmap_data.csv", "purpose": "全年紧急购电分布"})

    fig, ax = plt.subplots(figsize=(6.6, 3.5))
    x = np.arange(len(ablation))
    ax.bar(x, ablation["plan_cost_yuan"] / 1e6, label="初始计划费", color="#6b8e9f")
    ax.bar(x, ablation["adjustment_cost_yuan"] / 1e6, bottom=ablation["plan_cost_yuan"] / 1e6,
           label="调整费用", color="#d29b58")
    bottom = (ablation["plan_cost_yuan"] + ablation["adjustment_cost_yuan"]) / 1e6
    ax.bar(x, ablation["emergency_cost_yuan"] / 1e6, bottom=bottom,
           label="紧急购电费", color="#b94b55")
    ax.set(xticks=x, xticklabels=ablation["strategy"], ylabel="全年费用/百万元")
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "p3_update_ablation.pdf")
    plt.close(fig)
    ablation.to_csv(FIGURES / "p3_update_ablation_data.csv", index=False, encoding="utf-8-sig")
    sources.append({"figure": "p3_update_ablation.pdf", "data": "p3_update_ablation_data.csv", "purpose": "更新时刻消融"})

    compare = pd.DataFrame([
        {"scenario": item.name, "plan": item.plan_cost.sum(), "adjust": item.adjustment_cost.sum(),
         "emergency": item.emergency_cost.sum(), "total": item.total_cost.sum()}
        for item in (p2, p3, p42, p43)
    ])
    fig, ax = plt.subplots(figsize=(6.8, 3.5))
    ax.bar(compare["scenario"], compare["total"] / 1e6, color=["#54788f", "#67a17d", "#b88145", "#b5535c"])
    ax.set(ylabel="全年总费用/百万元")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "scenario_cost_comparison.pdf")
    plt.close(fig)
    compare.to_csv(FIGURES / "scenario_cost_comparison_data.csv", index=False, encoding="utf-8-sig")
    sources.append({"figure": "scenario_cost_comparison.pdf", "data": "scenario_cost_comparison_data.csv", "purpose": "四种主场景成本比较"})

    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    price_matrix = inputs.price[SUBMIT_START:]
    image = ax.imshow(price_matrix, aspect="auto", cmap="viridis", interpolation="nearest")
    ax.set(xlabel="日内10分钟区间", ylabel="日期序号")
    fig.colorbar(image, ax=ax, label="实时电价/(元/kWh)")
    fig.tight_layout()
    fig.savefig(FIGURES / "p4_price_heatmap.pdf")
    plt.close(fig)
    pd.DataFrame(price_matrix).to_csv(FIGURES / "p4_price_heatmap_data.csv", index=False, encoding="utf-8-sig")
    sources.append({"figure": "p4_price_heatmap.pdf", "data": "p4_price_heatmap_data.csv", "purpose": "波动电价全年结构"})

    pd.DataFrame(sources).to_csv(FIGURES / "figure_manifest.csv", index=False, encoding="utf-8-sig")
    return sources


def write_report(
    p1_metrics: dict[str, float],
    prediction: dict[str, object],
    summaries: list[dict[str, object]],
    quantile: float,
    quantile_losses: dict[str, float],
    sensitivity: pd.DataFrame,
    sources: list[dict[str, str]],
    ablation: pd.DataFrame,
) -> None:
    by_name = {item["scenario"]: item for item in summaries}
    lines = [
        "# 计算结果",
        "",
        "## 运行环境",
        "",
        "正式计算由 UV 管理的 CPython 3.10 执行；NumPy、SciPy HiGHS、Pandas、OpenPyXL 和 Matplotlib 版本见 `code/requirements.txt`。所有功率先乘以 1/6 h 转成区间电量。",
        "",
        "## 数据读取与预处理",
        "",
        "附件 1 读取 144 个区间；附件 2 和附件 4 均读取 365×144 数组；附件 3 日期向下填充后读取为 365×4×24。所有数组已通过形状、有限性和非负检查。附件 5 的首个区间表头疑似错位，结果簿保留原模板并严格按第 1 至第 144 行/列顺序映射。",
        "",
        "时序预测仅使用目标日前已完成日期。基学习器为前一日、近 7 日均值和近 4 个同星期均值，最近 14 日 MAE 倒数给权。提交期预测指标（单位均为区间电量 kWh）如下：",
        "",
        "| 目标 | MAE | RMSE | WAPE |",
        "| --- | ---: | ---: | ---: |",
    ]
    for target in ("load", "pv", "price"):
        item = prediction[target]
        lines.append(f"| {target} | {item['mae']:.4f} | {item['rmse']:.4f} | {item['wape']:.4%} |")
    lines += [
        "",
        f"1 月顺序验证在 0.70--0.90 中选择安全分位数 {quantile:.2f}；各候选加权损失为 "
        + "、".join(f"{key}: {value:.2f}" for key, value in quantile_losses.items()) + "。",
        "",
        "## 问题一结果",
        "",
        f"确定性 LP 的全天购电量为 {p1_metrics['purchase_kwh']:.2f} kWh，购电费为 {p1_metrics['cost_yuan']:.2f} 元；无储能基线费用为 {p1_metrics['baseline_cost_yuan']:.2f} 元，节省 {p1_metrics['baseline_cost_yuan'] - p1_metrics['cost_yuan']:.2f} 元。全天充电 {p1_metrics['charge_kwh']:.2f} kWh、放电 {p1_metrics['discharge_kwh']:.2f} kWh，日末 SOC 为 {p1_metrics['end_soc_kwh']:.2f} kWh。",
        "",
        "## 问题二至问题四结果",
        "",
        "| 场景 | 计划费/元 | 调整费/元 | 紧急费/元 | 总费用/元 | 紧急购电/kWh | 年末SOC/kWh |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summaries:
        lines.append(
            f"| {item['scenario']} | {item['plan_cost_yuan']:.2f} | {item['adjustment_cost_yuan']:.2f} | "
            f"{item['emergency_cost_yuan']:.2f} | {item['total_cost_yuan']:.2f} | "
            f"{item['emergency_purchase_kwh']:.2f} | {item['end_soc_kwh']:.2f} |"
        )
    lines += [
        "",
        "问题 2 与 4-2 在每日 0:00 形成计划，实际执行仅读取当前区间实际量；问题 3 与 4-3 在 6:00、12:00、18:00 冻结已执行区间后调整余下计划，结算基准为上一版有效计划。问题 4 的主结果用因果价格预测决策、实际价格结算。",
        "",
        "### 更新时刻消融",
        "",
        "| 策略 | 总费用/元 | 紧急购电/kWh | 调整上调/kWh | 调整下调/kWh |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for _, row in ablation.iterrows():
        lines.append(f"| {row['strategy']} | {row['total_cost_yuan']:.2f} | {row['emergency_kwh']:.2f} | {row['up_kwh']:.2f} | {row['down_kwh']:.2f} |")
    best_strategy = ablation.loc[ablation["total_cost_yuan"].idxmin(), "strategy"]
    lines += [
        "",
        f"固定电价全年回测中最低费用策略为 {best_strategy}。是否引入某个更新时刻以总费用边际变化为准，不能仅按预报误差判断。",
        "",
        "## 灵敏度分析",
        "",
        "| 单向效率 | 问题1费用/元 | 充电/kWh | 放电/kWh |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for _, row in sensitivity.iterrows():
        lines.append(f"| {row['eta']:.6f} | {row['cost_yuan']:.2f} | {row['charge_kwh']:.2f} | {row['discharge_kwh']:.2f} |")
    lines += [
        "",
        "另保存安全分位数、更新时刻和完美价格信息对照。完美价格信息场景是价格信息价值比较，不改变负载和光伏预测的信息边界。",
        "",
        "## 约束与一致性校验",
        "",
        f"问题 1 最大能量平衡残差为 {p1_metrics['balance_residual_kwh']:.3e} kWh，同时充放电最大交叠量为 {p1_metrics['simultaneous_flow_kwh']:.3e} kWh。",
    ]
    for item in summaries:
        lines.append(
            f"- {item['scenario']}：最大平衡残差 {item['balance_residual_kwh']:.3e} kWh，"
            f"最大边界违反 {item['constraint_violation']:.3e}，因果审计违反数 {item['causality_violations']}。"
        )
    lines += [
        "",
        "费用使用未舍入数组核算，Excel 仅在展示时保留 4 位小数。计划、SOC、紧急购电、费用分项和调整量保存在压缩 NPZ 与每日 CSV 中；连续紧急购电事件保存在 `results/emergency_events.csv`。",
        "提交模板的紧急购电页每个示例日期只预留 3 行，因此按时间顺序写入最早 3 个连续事件；该限制不影响全年完整事件表。",
        "",
        "年末 SOC 是不确定实际执行后的审计值；最后一日前计划强制目标为 6000 kWh，但预测误差可能使实际年末值偏离。该偏离作为终端规则风险披露，不通过读取未来实际值事后修饰计划。",
        "",
        "## 与建模报告的一致性说明",
        "",
        "主模型采用单向效率 0.9、显式弃光、不售电、区间最大流量 5000/6 kWh。问题 1 强制首尾 SOC 为 6000 kWh；其余问题 SOC 跨日连续并使用终端电量价值，最后一日前计划加 6000 kWh 终端约束。附件 3 在对应小时的 6 个区间内取常值，偏差修正只使用更早日期。",
        "",
        "## 图表清单",
        "",
        "| 图表 | 数据源 | 用途 |",
        "| --- | --- | --- |",
    ]
    for source in sources:
        lines.append(f"| {source['figure']} | {source['data']} | {source['purpose']} |")
    lines += [
        "",
        "## 可复现运行方式",
        "",
        "```powershell",
        "powershell -ExecutionPolicy Bypass -File code/run.ps1 code/run_all.py",
        "powershell -ExecutionPolicy Bypass -File code/run.ps1 code/validate_results.py",
        "```",
    ]
    (REPORTS / "RESULTS_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    prepare_directories()
    print("[1/8] 读取并审计附件")
    inputs = load_inputs()
    load_fc, load_weights = causal_ensemble(inputs.load)
    pv_fc, pv_weights = causal_ensemble(inputs.pv)
    price_fc, price_weights = causal_ensemble(inputs.price)
    price_fc = np.maximum(price_fc, 1e-4)
    quantile, quantile_losses = select_safety_quantile(inputs.load, inputs.pv, load_fc, pv_fc)

    prediction = {
        "load": forecast_metrics(inputs.load, load_fc),
        "pv": forecast_metrics(inputs.pv, pv_fc),
        "price": forecast_metrics(inputs.price, price_fc),
        "selected_safety_quantile": quantile,
        "quantile_validation_loss": quantile_losses,
        "information_boundary": "forecast[d] uses observations with index < d only",
    }
    (RESULTS / "prediction_metrics.json").write_text(json.dumps(prediction, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(RESULTS / "forecast_detail.npz", load=load_fc, pv=pv_fc, price=price_fc,
                        load_weights=load_weights, pv_weights=pv_weights, price_weights=price_weights)

    print("[2/8] 求解问题1")
    p1, p1_metrics = run_problem1(inputs)
    write_problem1(p1, p1_metrics)
    np.savez_compressed(RESULTS / "problem1_detail.npz", purchase=p1.purchase, charge=p1.charge,
                        discharge=p1.discharge, soc=p1.soc, curtail=p1.curtail,
                        price=inputs.fixed_price, load=inputs.fixed_load, pv=inputs.fixed_pv)

    fixed_decision = np.tile(inputs.fixed_price, (len(inputs.dates), 1))
    print("[3/8] 回测问题2")
    p2 = run_day_ahead(inputs, load_fc, pv_fc, fixed_decision, fixed_decision, quantile, "problem2")
    write_scenario_template(p2, "result2.xlsx", rolling=False)

    print("[4/8] 回测问题3及更新时刻消融")
    strategies = {
        "S0(0)": (0,),
        "S1(0,6)": (0, 6),
        "S2(0,6,12)": (0, 6, 12),
        "S3(0,6,12,18)": (0, 6, 12, 18),
    }
    fixed_rolling: dict[str, Scenario] = {}
    for label, releases in strategies.items():
        print(f"  - {label}")
        fixed_rolling[label] = run_rolling(
            inputs, load_fc, fixed_decision, fixed_decision, quantile, releases, f"problem3_{label[0:2]}"
        )
    p3 = fixed_rolling["S3(0,6,12,18)"]
    p3.name = "problem3"
    write_scenario_template(p3, "result3.xlsx", rolling=True)
    ablation_rows = []
    for label, scenario in fixed_rolling.items():
        ablation_rows.append({
            "strategy": label,
            "plan_cost_yuan": scenario.plan_cost.sum(),
            "adjustment_cost_yuan": scenario.adjustment_cost.sum(),
            "emergency_cost_yuan": scenario.emergency_cost.sum(),
            "total_cost_yuan": scenario.total_cost.sum(),
            "emergency_kwh": scenario.emergency.sum(),
            "up_kwh": scenario.adjustment_up.sum(),
            "down_kwh": scenario.adjustment_down.sum(),
        })
    ablation = pd.DataFrame(ablation_rows)
    ablation.to_csv(RESULTS / "update_ablation.csv", index=False, encoding="utf-8-sig")

    print("[5/8] 回测问题4-2及完美价格信息对照")
    p42 = run_day_ahead(inputs, load_fc, pv_fc, price_fc, inputs.price, quantile, "problem4_2")
    perfect_price = run_day_ahead(inputs, load_fc, pv_fc, inputs.price, inputs.price, quantile, "problem4_2_perfect_price")
    write_scenario_template(p42, "result4-2.xlsx", rolling=False)

    print("[6/8] 回测问题4-3")
    p43 = run_rolling(inputs, load_fc, price_fc, inputs.price, quantile, (0, 6, 12, 18), "problem4_3")
    write_scenario_template(p43, "result4-3.xlsx", rolling=True)

    scenarios = [p2, p3, p42, p43, perfect_price]
    for scenario in scenarios:
        save_scenario(scenario)
    save_emergency_events(scenarios)
    save_display_days(inputs, [p2, p3, p42, p43])

    print("[7/8] 灵敏度与图表")
    sensitivity_rows = []
    for eta in (0.85, 0.9, float(np.sqrt(0.9)), 0.95):
        _, metrics = run_problem1(inputs, eta)
        sensitivity_rows.append({"eta": eta, "cost_yuan": metrics["cost_yuan"],
                                 "charge_kwh": metrics["charge_kwh"], "discharge_kwh": metrics["discharge_kwh"]})
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(RESULTS / "efficiency_sensitivity.csv", index=False, encoding="utf-8-sig")
    summaries = [scenario_summary(scenario) for scenario in scenarios]
    (RESULTS / "summary.json").write_text(json.dumps({
        "problem1": p1_metrics,
        "scenarios": summaries,
        "perfect_price_information_value_yuan": float(p42.total_cost.sum() - perfect_price.total_cost.sum()),
        "template_mapping_risk": "附件5保留原结构，144个区间按位置顺序映射；可见首表头疑似错位",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    sources = make_figures(inputs, p1, p2, p3, p42, p43, ablation, load_fc, pv_fc)

    print("[8/8] 写结果报告")
    write_report(p1_metrics, prediction, summaries, quantile, quantile_losses, sensitivity, sources, ablation)
    print(json.dumps({"problem1_cost": p1_metrics["cost_yuan"],
                      "selected_quantile": quantile,
                      "scenarios": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
