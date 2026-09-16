# Round 5 Provider 对照 Closure

状态：`round5_closed_asymmetric_provider_outcome`

本轮只验证两个 Provider 在同一 frozen single-paper task、corpus、grounding 和 runtime 合同下的集成行为，不构成答案质量排名或严格模型能力比较。

## GLM

- Run：`dr-run-809f6d9fc01be667dceb6019`
- Provider/model：Zhipu BigModel / `glm-5.3-flash`
- terminal：`complete`
- Planner/Writer/Tool/Provider：1 / 1 / 4 / 2
- usage：4042 input / 1153 output / 5195 total
- cost：3231.0 micros CNY
- elapsed：7.8830546 s
- deterministic grounding：true；author review：true；publication ready：false
- replay：一致，外部调用 0

GLM artifact 已由历史 closure 记录并保持不变。

## DeepSeek

- Run：`dr-run-5b45d452661bd2204c0dfef1`
- Provider/model：DeepSeek / `deepseek-flash`
- terminal：`failed`
- error：`writer_content_truncated`
- HTTP：200；response JSON：已解析；model identity：已确认
- Writer：`finish_reason=length`，`output_tokens=4096`，最终 content 为空
- Planner/Writer/Tool/Provider：1 / 1 / 4 / 2
- usage：2836 input / 4526 output / 7362 total
- cost：6282.0 micros
- elapsed：18.5722525 s
- retries：0；fallback：0；outcome：known failure
- replay：一致，外部调用 0

准确解释是：DeepSeek 高推理模式下，项目固定的 Writer `max_tokens=4096` 不足；不能表述为 DeepSeek 官方最大输出只有 4096，也不能据此声称 DeepSeek 质量较低。

## 兼容性加固

- Planner/Writer 输出预算已成为显式 plan 字段，并传递到 Adapter、BudgetSpec、runtime reservation 和 telemetry；历史计划仍可显式使用 4096。
- 新增仅覆盖 `zhipu-bigmodel` 与 `deepseek` 的 capability profile。
- 新增统一 provider error class 与 retryability 标记；benchmark 的 `max_retries=0` 保持不变，截断、合同、认证错误不可重试。
- 新增离线 `provider_doctor` 和单段 PowerShell 入口，避免分段粘贴产生的 shell 语法错误。
- 未实施新的 Runtime、Provider、数据库、Web、Multi-Agent 或 execution/full-source fingerprint 拆分。

## 限制

两次结果不能用于最终答案质量排名：GLM 完成，DeepSeek 在 Writer 生成阶段已知失败。Evidence grounding、artifact 安全和 replay 语义均保持严格；语义正确性、开放域检索和长任务稳定性未验证。

后续可在 Round 6 进行最小 FastAPI/SSE/Demo/Release 封版，不再扩大 Provider 范围。
