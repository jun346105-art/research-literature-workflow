# Provider integration and recorded results

[Documentation](../README.md) · [Demo and scope](../DEEPRESEARCH_DEMO.md)

## Capabilities

The adapter layer records capability profiles for the implemented Zhipu BigModel and DeepSeek integrations, explicit Planner/Writer output budgets, normalized error classes and retryability. Retry is bounded by policy; the frozen comparison used zero retries. Replay reads the recorded artifacts with zero external calls. Credentials are supplied through server-side environment variables for explicitly authorized CLI runs.

Provider 层保留能力画像、显式预算、统一错误和有限重试策略；冻结对照的重试次数为 0。Replay 零外部调用，真实执行通过受控 CLI 与服务端环境变量完成。

Implementation: [capability profiles](../../src/litflow/deep_research/provider_profiles.py), [error normalization](../../src/litflow/deep_research/errors.py), [offline doctor](../../src/litflow/deep_research/provider_doctor.py), [controlled CLI script](../../scripts/run-provider-canary.ps1).

## Recorded outcomes and boundaries

| Recorded integration | Outcome | Interpretation |
|---|---|---|
| GLM-5.3-Flash | Complete | The frozen single-paper workflow completed with deterministic grounding and recorded human review. |
| DeepSeek | `writer_content_truncated` | The fixed 4096-token Writer budget was exhausted with high reasoning usage; no final content was returned. |

This is an integration/reliability record, not a model-quality ranking. The 4096-token limit was the project's frozen budget, not a claim about the provider's maximum capability. No selective successful rerun replaces these results.

这些结果展示固定任务与预算下的集成行为，不构成模型优劣排名。DeepSeek 的截断及此前失败记录均保留，不能用成功案例掩盖。

- [Full comparison, costs, replay and limitations](../deep_research/paired_e2e/ROUND5_PROVIDER_CLOSURE.md) · [result manifest](../deep_research/paired_e2e/round5_provider_closure.manifest.json).
- [Frozen paired plans and execution contract](../deep_research/paired_e2e/README.md).
- GLM attempts: [failure](../deep_research/paired_e2e/glm_attempt001_failure_closure.md), [partial](../deep_research/paired_e2e/glm_attempt002_partial_closure.md), [success](../deep_research/paired_e2e/glm_attempt003_success_closure.md).
- [DeepSeek canary design](../deep_research/deepseek/README.md) and [canary closure](../deep_research/deepseek/canary_closure.md).
- [GLM adapter contract](../deep_research/GLM_PROVIDER_CANARY_ADAPTER_V1.md), [replay boundaries](../deep_research/B03R2_REPLAY_BOUNDARIES.md) and [execution policies](../deep_research/EXECUTION_POLICIES_V1.md).
