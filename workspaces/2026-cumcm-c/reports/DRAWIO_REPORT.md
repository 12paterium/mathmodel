# DrawIO 图示生成报告

## 图示清单

| 文件 | 类型 | 来源依据 | 用途 | 状态 |
| --- | --- | --- | --- | --- |
| `figures/fig_roadmap.drawio` | 技术路线图 | 建模报告第 1 节及四问关系 | 放在问题分析或模型总览，说明预测、优化、执行和验证之间的关系 | 可编辑源文件已完成；PDF 待外部 DrawIO 导出 |
| `figures/fig_rolling_control.drawio` | 因果滚动控制流程图 | 建模报告第 7、8 节及结果报告的信息边界 | 放在问题 3 模型建立部分，并说明问题 4 沿用该框架 | 可编辑源文件已完成；PDF 待外部 DrawIO 导出 |

## 未生成图示及原因

未单独生成问题 1、问题 2 流程图和数据处理流程图。问题 1 是标准确定性线性规划，问题 2 与滚动控制图共享预测、优化和实际执行模块，继续拆图会与技术路线图重复。结果折线图、热力图和柱状图均由计算阶段生成，不在本阶段重复。

## 导出与自检记录

- 两个 `.drawio` 文件均采用未压缩 mxGraph XML，可由 diagrams.net 直接编辑。
- 节点按单向主流程排布；分支使用正交连线，未设置阴影和渐变。
- 当前机器未发现 `drawio`、`draw.io` 或 `draw.io.exe` 命令，因此未伪造 PDF 导出成功状态。
- 在具备 DrawIO CLI 的环境中执行：

```powershell
draw.io.exe --export --format pdf --crop --output figures/fig_roadmap.pdf figures/fig_roadmap.drawio
draw.io.exe --export --format pdf --crop --output figures/fig_rolling_control.pdf figures/fig_rolling_control.drawio
```

## 给论文阶段的嵌入建议

- `fig_roadmap`：建议 caption 为“微网电力调控建模与验证技术路线”。
- `fig_rolling_control`：建议 caption 为“基于因果信息边界的滚动计划调整流程”。
- PDF 未导出前，论文不应引用不存在的文件；可先保留图位，验收时将外部工具缺失列为明确风险。
