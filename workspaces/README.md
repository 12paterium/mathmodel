# 比赛工作区

每场比赛建立一个独立子目录，例如 `workspaces/2026-cumcm-a/`。进入该目录后，把题面和附件放在 `problem/`，再按项目根目录的 [docs/WORKFLOW.md](../docs/WORKFLOW.md) 执行主工作流。

建议的最小结构：

```text
<contest-name>/
└── problem/
    ├── statement.pdf
    └── data/
```

启动 skill 会在该工作区继续创建 `plan.md`、`todo.md`、`reports/`、`code/`、`results/`、`figures/` 和 `paper/`。题面原件应保持不变；清洗后的数据和派生数据放到代码阶段约定的输出目录，并在报告中说明来源。
