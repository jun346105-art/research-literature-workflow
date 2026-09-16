# Historical GLM Attempt-002 Partial Closure

只读核验目录 `outputs/deep_research/e2e/v1.2/dr-run-e5303a3ece54a1758d625415`；保留原 6 个文件，不回写 artifact。

状态为 `partial`：provider operations 2（Planner 1、Writer 1）、tool calls 4、retry 0，usage `3108/787/3895`，cost `2345` micros CNY，elapsed `6.0491241s`。deterministic grounding 为 true，claims/citations 为 `3/3`，author review required 为 true，publication ready 为 false，gaps 为 2。

两个 gap 由 `evidence_to_subtask` 单值覆盖缺陷产生，属于 `generic_runtime_defect`；该历史 run 不可恢复。`partial` 仍是业务安全 partial，CLI 映射为 exit 2，不改为 complete。新 Attempt-003 使用独立 identity。

机器核验见 [glm_attempt002_partial_closure_manifest.json](glm_attempt002_partial_closure_manifest.json)。
