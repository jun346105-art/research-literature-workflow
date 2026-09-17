# Gate A Canary Design v1

Batch `B08 / S19` design freeze only. Provider: Zhipu BigModel ordinary model API; model ID `glm-5.3-flash`; endpoint `https://open.bigmodel.cn/api/paas/v4/chat/completions`. Coding Plan and `glm-5.3-flash[1m]` are excluded.

Official sources reviewed 2026-08-27: [model page](https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash), [release](https://docs.bigmodel.cn/cn/update/new-releases), [thinking](https://docs.bigmodel.cn/cn/guide/capabilities/thinking), [Chat Completion](https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E5%AF%B9%E8%AF%9D%E8%A1%A5%E5%85%A8), [Coding Plan distinction](https://docs.bigmodel.cn/cn/coding-plan/latest-model).

Frozen text-only synthetic JSON probe: `temperature=1`, `top_p=0.95`, `thinking.type=enabled`, `reasoning_effort=max`, input 512, output 256, one call, zero retries, 30-second operation timeout, 45-second deadline. No tools, vision, video, files, Web, parallelism, fallback, replan, status lookup or final report.

Official pricing is not sufficiently verified: `monetary_budget_status=blocked_pending_official_pricing`; no price is inferred. Design is pass; adapter implementation may proceed offline later; real Canary execute remains blocked pending official pricing and separate user authorization. Future preflight checks ordinary-API credential-channel compatibility without reading a credential value.

## Closure status

The later, separately authorized v1.2 attempt-003 execution is recorded in [Gate A Canary Result v1](GATE_A_CANARY_RESULT_V1.md) as `pass_text_only_single_call`. This preserves the original design-freeze record and does not expand the verified scope beyond one GLM-5.3-Flash text-only single call.
