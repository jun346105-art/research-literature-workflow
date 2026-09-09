# B08E2E-R1 — Attempt-002 Planner Contract Incident and Minimal Repair

Status: `completed` / offline repair only; no Key, HTTP, retry or new real E2E.

## Attempt-002 evidence

The preserved artifact remains immutable:

- `runtime.jsonl`: 4,986 bytes, SHA-256 `861529b73dc441a6496cde6d75b612c2775a7a7e6179ef1a48c8d0aa1bcddd6d`
- `checkpoint.json`: 1,914 bytes, SHA-256 `92999908b495a2aab541d5180cf05280700187a127dd367cfde0d10e25fd2135`

The stream proves a durable Planner `operation_dispatched` followed by `operation_failed` with `planner_contract_invalid`; it records no provider usage and no tool call. The checkpoint remained `researching` and contained no response envelope, finish reason, response content hash, or structural diagnostics. Therefore the exact historical root cause is `not_provable`; this record does not infer truncation or a schema defect.

## Minimal repair

The E2E boundary now keeps the existing B03R2 event/replay semantics and adds only:

- layered provider diagnostics with HTTP status, response/JSON/model/usage booleans, finish reason, content length/hash, observed type/allowlisted keys, failure stage, error code and safe Pydantic type/location;
- one-layer JSON code-fence normalization;
- separate `transport_failure`, `provider_response_invalid`, `planner_content_truncated`, `planner_json_invalid`, `planner_schema_invalid`, `planner_scope_invalid` and `planner_dependency_invalid` outcomes;
- known Planner failure → durable `failed` lifecycle/checkpoint and CLI exit `2`;
- Planner unknown → durable `operation_unknown`, manual-intervention exit `3`, no Writer, no retry;
- replay remains provider/tool/Writer-free.

No raw response, Authorization, key, private path or full Planner text is persisted. Planner output token budget remains unchanged at 256 because this audit had no evidence that output truncation caused Attempt-002.

Attempt-003 is frozen separately at [the v1.1 plan](../e2e/v1.1/glm_e2e_pilot_plan.attempt-003.json) with a new attempt ID, run ID and artifact target.
