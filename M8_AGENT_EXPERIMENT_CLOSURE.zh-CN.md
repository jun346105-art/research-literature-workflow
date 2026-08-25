# M8 Experimental Agent Closure

## Final Status

- M8A controlled single-agent scaffold = `pass`
- M8B.1A durable event/replay kernel = `pass`
- M8B.1B progress-aware control plane Fake E2E = `pass`
- M8B.1B AG01 real Flash planning/tool chain = `pass`
- M8B.1B AG01 end-to-end grounded answer = `fail_at_quote_grounding`
- AG07/AG11 real Flash canary = `not_run_due_to_gate`
- 12-task pilot/stability evaluation = `not_run`
- end-to-end grounded agent completion = `not_validated`
- Agent extension overall = `experimental_partial_pass`

## Verified Engineering Capability

The extension implements a controlled LangGraph single Agent with schema-bound tools, deterministic policy gates, dynamic tool routing, bounded calls, repeated-call handling, partial coverage semantics, and human approval interrupts. Its v2 durable event log is append-only and hash-chained; it records provider steps, tool batches, call/result identity, approval/internal-control-plane identity, state projection, checkpoint/resume validation, and offline canonical request replay.

## Real Flash Canary Fact

AG01 completed the real planning/tool chain:

```text
list_papers -> retrieve_evidence -> answer_grounded
```

The AG01 provider usage was 4 calls, 14,388 input tokens, 808 output tokens, and 15,196 total tokens. Planner, Policy Gate, Tool Executor, and Durable Trace ran normally. Citation passages came from the current Top-10; qrels/gold leakage, unauthorized tools, repeated execution, and budget violations were all absent.

## Gate Failure and Stop-Loss

The final QA validation failed with `quote_grounding_failed / evidence_anchor_not_found`. The answer was not displayed as verified. This is an end-to-end grounded-answer failure, not a claim that the planning/tool-control chain failed.

The frozen gate requires AG01 success before AG07/AG11. Therefore AG07/AG11 real Flash canaries, 12-task pilot, and stability evaluation were not run. No retry, Prompt change, QA validator change, quote mapper change, retriever change, model switch, or further Agent development is authorized.

## Not Validated

The project does not claim a passed Agent task-completion benchmark, production-ready Agent behavior, stable grounded-answer generation, multi-Agent capability, MCP completion, or autonomous long-horizon research.

## Optional Future Directions

Future work, if separately approved, could ask the model to select evidence/span identity while the program deterministically extracts the exact original quote. This document records a direction only; it does not add code or alter the frozen QA/Agent contracts.
