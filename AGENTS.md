# 项目级工作约定

本项目是数学建模竞赛 skill 库，不是一篇具体论文。可复用的 skills 保存在 `skills/`；每场比赛的题面、数据、代码、图表、报告和论文都必须放在 `workspaces/<contest-name>/` 下，避免把比赛产物混入 skill 库。

## 执行入口

当用户要求开始或推进一场数学建模比赛时：

1. 先确认当前目录是否为对应的 `workspaces/<contest-name>/`。没有比赛工作区时，先建立它并读取 `workspaces/README.md`。
2. 读取 [docs/WORKFLOW.md](docs/WORKFLOW.md) 和 [docs/PAPER_WRITING_BRIEF.md](docs/PAPER_WRITING_BRIEF.md)。
3. 按顺序读取并执行 `skills/1start-mathmodel`、`2analysis-modeling`、`3coding-visual`、`4drawio`、`5writing`、`6verity`。阶段完成后更新工作区内的 `todo.md`。
4. 只在用户明确要求时触发 `doctor`；Typst 语法或排版问题才按需读取 `typst-author`；需要复用科研图表时才读取 `mathmodel-figure-templates`。

## 证据和边界

- 题面、附件、代码输出和报告是事实来源；无法从这些来源确认的内容必须标记为假设、待核实或风险。
- 论文不得编造数值、实验结果、引用、数据字段或图表结论。摘要中的数值应在正文和结果报告中保持一致。
- 每个阶段只修改自己的产物范围，并读取前序阶段的报告作为输入。遇到模型问题回退到分析阶段，不在写作阶段悄悄改写模型。
- 每个数据型图表都要能追溯到代码和数据；每个非数据型图示都要保留可编辑源文件。
- 论文正文不得暴露 `reports/`、`code/`、`figures/`、`skills/` 等内部组织细节。

## 完成标准

只有当工作区同时具备完整的分析报告、结果报告、必要图表、论文入口文件、可复现运行方式和 `reports/VERIFY_REPORT.md`，并且验收报告明确给出 `PASS` 或记录了可接受的外部工具缺失原因，才可把论文称为完成。

项目结构、阶段产物和质量门槛的唯一详细说明见 [docs/WORKFLOW.md](docs/WORKFLOW.md)。本文件只保留每次运行都需要知道的规则。
