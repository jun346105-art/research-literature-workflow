# M8B.1 Design Mapping

| Upstream mechanism | LitFlow current behavior | Gap | Decision | Local implementation |
| --- | --- | --- | --- | --- |
| Harness step = one request plus all tool calls | Each queued tool call re-enters `planner` as if it were a separate model decision | A provider parallel batch is not a first-class step | Adapt | One durable `ToolBatch` with model order and per-call policy records |
| Durable `tool/call` then immutable `tool/result` | `tool_calls` contain only final refs; raw result and call identity are absent | No call/result pairing or replayable context | Adopt | Append-only event records with call ID, normalized args, result, verification, latency, and usage |
| Model-visible context is derived from log | `NativeToolPlanner._safe_observations()` rebuilds an in-memory summary of refs only | Tool values, coverage, remaining budget, and steering are not reproducible | Adopt | Deterministic context renderer exclusively from durable events and typed state |
| Model-order result delivery | Parallel calls are queued but not correlated with a model call ID | Ordering cannot be audited end-to-end | Adapt | Serial execution is retained, while original tool-call order is preserved in one batch |
| Request-time tool visibility | All six schemas are sent on every planner request | Completed/irrelevant tools remain callable | Adapt | Derive `allowed_next_actions` from progress state before each model request |
| Monotonic guards | Existing allowlist/argument checks exist | A later state cannot explicitly prove a refusal stays refused | Adopt | Immutable denied result plus monotonic policy state |
| Soft vs hard limits | Two retrieval calls are a hard failure | Useful evidence can become an execution failure before wrap-up | Adapt | Soft retrieval limit removes retrieval and injects one deterministic steering message; hard budgets remain terminal |
| HITL interrupt and resume | LangGraph interrupt exists | Matrix completion is not represented as durable progress and can be requested twice | Adapt | Persist matrix-loaded state and approval event; expose stage tool only after approval |

This mapping is a design record, not an implementation claim. M8B.1 implementation is blocked until the trace invariant is first restored and verified.
