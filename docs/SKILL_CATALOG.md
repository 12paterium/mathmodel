# Skill 清单

## 主工作流

| Skill | 触发时机 | 读取重点 | 交接物 |
| --- | --- | --- | --- |
| `1start-mathmodel` | 新建或重启比赛项目 | 用户偏好、题面概况、规范参考 | `plan.md`、`todo.md` |
| `2analysis-modeling` | 题面和附件已可读取 | 子问题、歧义、变量、目标、约束、算法 | `reports/ANALYSIS_MODELING_REPORT.md` |
| `3coding-visual` | 建模报告完成 | 可复现实现、约束验证、实验、数据图 | `code/`、`results/`、`figures/`、结果报告 |
| `4drawio` | 需要技术路线或流程图 | 非数据图需求、DrawIO 源文件、导出检查 | `figures/*.drawio`、PDF、图示报告 |
| `5writing` | 结果和图表稳定 | 比赛模板、语言、引擎、章节、图表嵌入 | `paper/` |
| `6verity` | 论文候选版本完成 | 文本门禁、结构、图表、数值、编译、视觉检查 | `reports/VERIFY_REPORT.md` |

## 辅助 skill

| Skill | 触发时机 | 作用 |
| --- | --- | --- |
| `doctor` | 用户明确要求环境检查 | 检查编译器、Python 包、DrawIO 和 PDF 工具 |
| `typst-author` | 选择 Typst 或遇到 Typst 排版问题 | 按需提供 Typst 语法和排版参考 |
| `mathmodel-figure-templates` | 用户要求复用科研图表模板 | 从本地脚本生成 PNG/PDF/SVG，支持 11 类模板 |
| `_references` | 阶段 skill 按需读取 | 数学建模、题型防错、图表和论文规范；不单独触发 |

## 调用规则

主工作流按数字前缀顺序执行。辅助 skill 不改变主阶段顺序。一个阶段完成后，下一阶段读取前序报告，而不是依赖对话中未落盘的结论。

所有 skill 的实现和模板都属于工具层；比赛中的临时文件、生成脚本副本和结果必须写入当前 `workspaces/<contest-name>/`。
