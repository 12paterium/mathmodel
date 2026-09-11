# 项目布局说明

## 两个层次

项目分为“工具层”和“比赛层”：

| 层次 | 位置 | 生命周期 | 内容 |
| --- | --- | --- | --- |
| 工具层 | `skills/` | 长期复用 | SKILL.md、模板、脚本、共享规范 |
| 比赛层 | `workspaces/<contest-name>/` | 每场比赛独立 | 题面、数据、模型报告、代码、图表和论文 |

模型运行具体比赛时，应把比赛层作为当前工作目录；工具层通过相对路径或项目根目录路径读取。

## `skills/` 的组织规则

每个可触发 skill 必须是 `skills/<skill-name>/SKILL.md`。工作流 skill 的目录名保留数字前缀，因为它表达推荐顺序并且被现有文档引用。`_references` 是共享参考资料，不是独立执行阶段。

一个 skill 的附属内容与它的 `SKILL.md` 同目录保存：

- `scripts/`：可执行脚本；
- `templates/`：论文模板或代码模板；
- `references/`：只在该 skill 分支触发时读取的参考内容；
- `assets/`：预览图或其他只读资源。

不要把一个 skill 拆到多层分类目录下，除非同步更新发现机制和全部相对引用。保持 skill 目录扁平可以让当前的项目加载方式继续工作。

## 比赛层的所有权

| 目录/文件 | 责任阶段 | 说明 |
| --- | --- | --- |
| `problem/` | 用户/分析阶段 | 原始题面和附件，保留原件 |
| `plan.md`、`todo.md` | 启动阶段 | 方案、偏好和进度 |
| `reports/ANALYSIS_MODELING_REPORT.md` | 分析阶段 | 数学模型和代码接口 |
| `code/`、`results/` | 代码阶段 | 可复现实现和数值证据 |
| `figures/` | 代码/图示阶段 | 数据图和非数据图 |
| `reports/RESULTS_REPORT.md` | 代码阶段 | 结果、校验、运行记录 |
| `reports/DRAWIO_REPORT.md` | 图示阶段 | 非数据图清单和嵌入建议 |
| `paper/` | 写作阶段 | 论文源文件和编译产物 |
| `reports/VERIFY_REPORT.md` | 验收阶段 | 提交前结论和遗留问题 |

## 路径约定

论文章节位于 `paper/sections/` 时，引用 `figures/` 使用 `../../figures/...`；论文入口位于 `paper/` 时，使用 `../figures/...`。具体以实际文件位置为准，不能把模板中的示例路径直接照搬到另一个层级。
