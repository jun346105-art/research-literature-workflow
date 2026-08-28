# GLM Provider Canary Adapter v1

The B08/S19 adapter is a deliberately narrow, text-only, non-streaming ordinary-model API integration for `glm-5.3-flash` at `https://open.bigmodel.cn/api/paas/v4/chat/completions`. It uses Python standard-library `urllib`, sends one fixed synthetic JSON probe, and has no tools, Web, vision, video, files, parallel calls, fallback, retry, status lookup, Planner, Writer, Multi-Agent or Critic behavior.

`GLMCanaryRunner` is the only public live-capable entry. Its internal adapter is not exported by `litflow.deep_research`. At execute time only, the runner checks the named `ZHIPUAI_API_KEY` environment variable before creating any artifact or durable dispatch. It then preserves the B03R2 ordering: journal, budget reservation, durable `operation_reserved`, durable `operation_dispatched`, invocation, durable terminal event, checkpoint and deterministic replay. Missing configuration and reservation/dispatch fsync failure invoke no transport. Timeout or connection ambiguity yields `outcome_unknown`, retains the reservation and returns `ManualInterventionRequired`; it never retries or re-dispatches.

The active user-confirmed promotional pricing snapshot is 0.4 CNY per million input tokens and 1.4 CNY per million output tokens. The reservation uses the fixed 512/256 ceiling and the hard 0.01 CNY ceiling. Terminal accounting derives actual cost only from provider `usage`; it does not estimate usage from text length. The adapter redacts credentials and authorization headers from runtime events, checkpoints and artifacts.

This is an offline-verified transport boundary, not a completed provider Canary, DeepResearch Agent E2E result, or exactly-once remote-execution guarantee.
