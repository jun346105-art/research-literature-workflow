# Historical GLM Attempt-001 Failure Closure

本 closure 只读核验既有目录 `outputs/deep_research/e2e/v1.2/dr-run-f8d0cba03855233691766953`，不修改其中 3 个文件。

结论：`failed_known_preexisting_http_401`。来源 `not_provable`；本次用户 CLI 未 dispatch。durable stream 记录 provider dispatch 1、Planner 1、Writer 0、Tool 0、retry 0；usage `0/0/0`、cost `0`；elapsed `1.4016112s`。checkpoint/hash-chain/replay 与 secret/private-path 检查均通过。

这不是新的 Provider 执行，也不构成 GLM 可用性或模型质量结论。新配对实验使用独立 Attempt-002 identities。

机器记录见 [glm_attempt001_failure_closure_manifest.json](glm_attempt001_failure_closure_manifest.json)。
