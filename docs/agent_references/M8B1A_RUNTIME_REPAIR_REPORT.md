# M8B.1A Durable Event & Replay Kernel Repair Report

## Result

`passed_offline_kernel_validation`. This is not an M8B.1 behavior or Flash Canary result.

## Fixed foundation

- Native provider decisions can now be represented as one provider step and one model-ordered tool batch.
- Tool calls receive provider IDs when present or deterministic synthetic IDs otherwise.
- Success, denial, invalid arguments, execution errors, and skip states use a single terminal-result contract.
- Model-visible result content is durable, sanitized, hashed, and rendered into subsequent planner context by the same function used for offline replay.
- Event log projection is the source for replayable state; legacy trace replay explicitly reports nonreplayable status.
- Resume validates the event-derived projection before continuing a LangGraph interrupt.

## Fake validation

`outputs/m8_agent/m8b1a_fake_runtime_validation/` records a zero-provider validation run. It confirms a Chinese UTF-8 request, durable retrieval result, result-to-next-request visibility, terminal pairing, request SHA equality, and projection reconstruction.

## Still intentionally out of scope

No Dynamic Tool Surface, Soft Budget routing, turn-stopping steering, entity-aware allowance, planner strategy, Flash call, M8B.1 Canary, Pilot, or Stability trial is included. The next phase requires explicit approval for `M8B.1B Progress-Aware Control Plane + Canary`.
