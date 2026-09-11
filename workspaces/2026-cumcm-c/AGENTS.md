# C 题工作区约定

本目录是 2026 年高教社杯全国大学生数学建模竞赛 C 题“微网与外部电网电力调控策略”的独立工作区。所有本题产物只能写在本目录内。

## 新对话启动顺序

1. 先读本文件、`PROBLEM.md`、`plan.md`、`todo.md`。
2. 再读 `reports/ANALYSIS_MODELING_REPORT.md`，将其视为编程阶段的模型规格。
3. 回到项目根目录读取 `../../docs/WORKFLOW.md`、`../../docs/PAPER_WRITING_BRIEF.md`。
4. 当前应从 `../../skills/3coding-visual/SKILL.md` 开始，完成后依次执行 `4drawio`、`5writing`、`6verity`；每完成一阶段立即更新 `todo.md`。
5. 不要重做已完成的 `1start-mathmodel` 和 `2analysis-modeling`，除非编程验证发现模型错误；若发现错误，应明确回退并更新建模报告。

## 当前状态

- 工作区、题面、附件、计划和建模报告已经建立。
- `2analysis-modeling` 已完成；`3coding-visual` 尚未实现。
- `problem/solve_p1.py`、`problem/make_result1.py`、`problem/p1_solution.npz` 和 `problem/result1.xlsx` 是探索材料，只能用于对照，不能当作正式结果。
- 项目内 Python 环境已经配置，详见“运行环境”。

## 必须遵守的建模口径

- 一天 144 个 10 分钟区间，功率乘以 `1/6 h` 后才是区间电量。
- 储能 SOC 范围为 `[1200, 10800] kWh`，区间最大充/放电量为 `5000/6 kWh`，初始 SOC 为 `6000 kWh`。
- 主模型采用充电效率和放电效率分别为 `0.9`；往返效率为 `0.81`。其他解释只做灵敏度分析。
- 使用带显式弃光量的等式能量平衡；不允许售电。
- 问题 1 强制日首尾 SOC 均为 6000 kWh。
- 问题 2 至 4 严格遵守因果信息边界，制定计划时不得读取当日未来实际负载、光伏或价格。
- 问题 3 的小时光伏预报主方案在对应小时的 6 个区间内取常值；调整只修改尚未执行区间，并相对上一版有效计划结算。
- 问题 4 主结果使用因果价格预测制定计划、实际价格结算，同时计算完美价格信息下界。
- 附件 5 的首个购电区间表头疑似错位。必须保留模板结构并按 144 行的顺序映射，在结果报告中披露风险。

更完整的公式、歧义说明、预测方案、输出接口和验收阈值见 `reports/ANALYSIS_MODELING_REPORT.md`，不得在编码阶段无记录地改变。

## 运行环境

- Python：UV 管理的 CPython 3.10。
- 隔离依赖目录：`code/_vendor/`。
- 已安装：NumPy 2.2.6、SciPy 1.15.3、Pandas 2.3.3、OpenPyXL 3.1.5、Matplotlib 3.10.9。
- 首次重建：在本目录执行 `powershell -ExecutionPolicy Bypass -File code/bootstrap.ps1`。
- 运行脚本：`powershell -ExecutionPolicy Bypass -File code/run.ps1 code/<script>.py [参数]`。
- 不要调用裸 `python`，它可能指向不可用的 Windows Store 别名。
- 依赖版本记录在 `code/requirements.txt`；不要把新依赖装到全局 Python。

## 编程阶段交付要求

按问题 1、2、3、4 的顺序逐问实现、运行和校验，不要一次性写完后才测试。正式实现放在 `code/`，结果放在 `results/`，数据型图表放在 `figures/`，并生成 `reports/RESULTS_REPORT.md`。

最终必须生成：

- `results/result1.xlsx`
- `results/result2.xlsx`
- `results/result3.xlsx`
- `results/result4-2.xlsx`
- `results/result4-3.xlsx`

同时保存机器可读的预测指标、成本分解、约束残差、灵敏度结果、图表源数据和运行日志。所有等式最大残差不高于 `1e-6 kWh`，费用分项核对误差不高于 `0.01 元`。

## 完成定义

只有在分析报告、结果报告、必要图表、可编辑非数据图、LaTeX 论文入口、可复现命令和 `reports/VERIFY_REPORT.md` 全部存在，并且验收报告给出 `PASS` 或说明可接受的外部工具缺失时，才能称本题完成。

