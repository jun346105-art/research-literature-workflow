# Historical DeepSeek Canary Closure

本 closure 只读核验既有 artifact：`outputs/deep_research/canary/v1/dr-run-0381179dd264e4f8324c3214`。artifact 未被重写或修复。

核验事实：terminal `complete`；HTTP 200；model identity verified；application contract valid；usage `70/69/139`（input/output/total）；cost `103.8` USD micro-units；provider calls 1；retries 0；replay calls 0；event hash chain、checkpoint hashes 和 checkpoint replay 一致；secret/private-path scan clean。

已知边界：历史 artifact 没有持久化 cache hit/miss split，且 client elapsed 为 `0`。因此本 artifact 不用于 cache-aware 费用拆分或延迟对照。后续 runtime 已增加安全 cache split 与 monotonic elapsed 遥测；不会回写本历史 artifact。

机器核验结果见 [canary_closure_manifest.json](canary_closure_manifest.json)。
