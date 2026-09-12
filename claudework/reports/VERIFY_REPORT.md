# C 题验收报告

验收对象：`claudework/` 下的模型、代码、结果与论文。复现命令与结果如下。

## 一、复现路径

```bash
# 环境（首次）
uv venv claudework/.venv --python 3.12
uv pip install --python claudework/.venv/Scripts/python.exe numpy pandas scipy openpyxl matplotlib

# 结果与校验（约 30 秒）
cd claudework/code
../.venv/Scripts/python.exe run_all.py       # 五个结果文件 + reports/run.log
../.venv/Scripts/python.exe verify_output.py # 回读结果文件核对结构
../.venv/Scripts/python.exe figures.py       # 六张矢量图

# 论文（两遍，约 20 秒）
cd claudework/paper
xelatex main.tex && xelatex main.tex
```

## 二、硬性阈值核对

| 检验项 | 阈值 | 实测最大值 | 结论 |
| --- | --- | --- | --- |
| 能量平衡等式残差 | ≤ 1e-6 kWh | 4.6e-13 kWh | PASS |
| 储电量边界违反 | ≤ 1e-6 | 3.6e-12 | PASS |
| 充放电功率边界违反 | ≤ 1e-6 | 1.8e-12 | PASS |
| 售电（负购电量） | 0 | 0 | PASS |
| 费用分项之和与总费用 | ≤ 0.01 元 | 0（同一表达式求和） | PASS |
| 分段值之和 vs 全天购电量 | — | 1.5e-11（四位小数舍入） | PASS |

## 三、交付物完整性

| 交付物 | 状态 | 说明 |
| --- | --- | --- |
| `results/result1.xlsx` | 存在 | 144 段购电量 + 6 时段充放电量 + 首尾储电量 |
| `results/result2.xlsx` | 存在 | 334 天 × 144 段，充放电量 2005 行，紧急购电 3531 条 |
| `results/result3.xlsx` | 存在 | 计划购电量、调整购电量、充放电量、紧急购电量四表齐全 |
| `results/result4-2.xlsx` | 存在 | 波动电价下的问题 2 |
| `results/result4-3.xlsx` | 存在 | 波动电价下的问题 3 |
| `results/summary.json` | 存在 | 各问费用汇总 |
| `reports/RESULTS_REPORT.md` | 存在 | 模型、结果、校验、可改进方向 |
| `figures/*.pdf` | 存在 | 6 张矢量图 |
| `paper/main.pdf` | 存在 | 26 页，两次编译无未定义引用 |
| `paper/main.tex` + `paper/sections/` | 存在 | 11 个章节文件 + 参考文献 + 代码附录 |

## 四、结果文件回读核对

对五个结果文件做独立回读（不依赖生成时的内存状态）：

- `result2.xlsx` 计划购电量：形状 (334, 144)，无空值；每行 144 个分段值之和与该行“全天购电量”列最大偏差 1.5e-11。
- `result2.xlsx` 充放电量：2005 行 = 1 + 334×6，日期列 334 天全覆盖无空。
- `result2.xlsx` 紧急购电量：3531 条连续区间，电量合计 343800.18 kWh，与程序内统计一致。
- `result1.xlsx` 计划购电量合计 57580.9813 kWh，与 `summary.json` 一致。

## 五、因果性核对

- 问题二至四：第 d 天的预测只读取 `series[lo:day]`（上界为 day 的开区间），不存在读取当天未来的路径。
- 问题三：发布时刻 r 的调整只重排区间 `[6r, 144)`，已执行区间不再改动；`pv_forecast_after` 只取附件 3 中发布时刻不晚于 r 的预报。
- 已用 2025-06-21、2025-07-15、2025-05-01 三天的逐小时曲线人工核对附件 3 的时间对齐，逐格吻合。

## 六、已知限制

1. **模板表头错位**：附件 5 的“计划购电量”表头从 `0:10-0:20` 开始，比当天实际区间整体错开一格。本文不改模板结构，按行号映射（第 2 行 → 区间 0），已在论文与结果报告中披露。
2. **储能严格按计划充放电**：这是式(1) 恒等式成立的前提，也意味着执行阶段不能自适应。若放开，紧急购电还能下降，但充放电量会偏离计划。
3. **附件 3 预报精度**：实测其误差约为“前 7 天实际均值”的 2.4 倍，导致问题三总费用高于问题二。这是数据集性质，已在论文中如实报告。
4. **日循环约束**：问题二至四要求每天 24:00 回到 0:00 电量。放开后由于残值折现会出现“储能长期顶在上限”的退化解，反而更贵。

## 七、结论

硬性阈值全部 PASS，交付物齐全，全流程可一键复现，因果性经人工核对。
论文经两次 xelatex 编译无未定义引用或硬错误。

**验收通过。**
