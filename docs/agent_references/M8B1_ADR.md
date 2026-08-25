# ADR: M8B.1 Progress-Aware Harness Closure

## Status

Blocked by foundational trace/replay defect found in M8B Canary audit.

## Decision

Keep LitFlow's existing LangGraph `StateGraph` and its eight nodes. If and only if durable model-visible trace reconstruction is first demonstrated, add a small Python control plane for tool batches, dynamic tool exposure, typed progress state, soft retrieval steering, and hard-budget enforcement.

## Invariants

1. A step is one provider decision and every native tool call it returned.
2. Each call independently receives pre-execute policy, monotonic guard, execution, post-execute verification, and one immutable result.
3. Model-visible tool results, coverage, remaining budget, and steering are append-only durable events and replay byte-for-byte into the same context renderer.
4. Soft retrieval limits produce a grounded wrap-up opportunity; only hard limits produce `budget_exhausted`.
5. Completed Matrix queries are removed from the tool surface. Approval precedes any writing call or artifact.

## Rejected alternatives

- Replace LangGraph with DeepSeek Harness, Deep Agents, or PydanticAI: rejected because it duplicates runtime scope and imports generic coding-agent capabilities.
- Add task or paper-specific planner rules: rejected because this hides the observed control-plane defect.
- Use qrels, gold passages, or expected task assertions in runtime steering: rejected because that leaks evaluation information.
- Make parallel provider calls concurrent: rejected for M8B.1; sequential, model-order execution is simpler and replayable.

## Consequence

The prescribed M8B.1 Flash Canary must not run until the trace audit reports replayable model-visible context. The current failure is an engineering runtime defect, not evidence that the QA validator, retriever, or historical MVP needs changing.
