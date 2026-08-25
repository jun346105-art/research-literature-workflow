# Durable Agent Event Schema v2

## Scope

This schema is for future M8B.1A runs only. Historical M8A/M8B traces remain `trace_schema_version=1` and `replay_capability=legacy_nonreplayable`.

## Turn and provider step

`turn_started` records `turn_id`, `task_id`, schema version, and frozen run identity. A `provider_request` is durably recorded before provider dispatch and includes canonical messages/tools plus their SHA-256 values. A following `provider_step` records model identity, ordinal, provider request ID when available, usage, latency, finish reason, pre-provider request hashes, and the request event boundary.

One provider step owns one `tool_batch`. A batch records its original model order. Every `tool_call` contains a provider ID or deterministic ID, canonical arguments, argument SHA, ordinal, and policy/execution state. Every call has exactly one immutable terminal `tool_result`: `success`, `denied`, `invalid_arguments`, `execution_error`, `skipped_due_to_budget`, `skipped_due_to_prior_failure`, or `cancelled`.

## Model-visible content

Each terminal result stores both a full internal-result SHA and the exact sanitized `model_visible_content` sent into the next planner request. Result references alone are not enough. Events must not contain credentials, authorization headers, qrels/gold data, or private paths.

## Integrity and replay

Events are UTF-8 JSONL with stable key ordering and separators. Each event has `event_seq`, `previous_event_sha256`, `event_sha256`, and a deterministic timestamp in fake validation. Hash-chain gaps, duplicate sequence numbers, malformed JSON, missing terminal results, or projection mismatch fail closed.

`render_planner_request(events, projection, allowed_tools)` is the only canonical request renderer. Online planning and offline replay use it. “Byte-for-byte replay” means canonical pre-provider request payload equivalence, not provider tokenization, HTTP headers, TLS traffic, or provider-internal serialization.

## State projection

The Event Log is authoritative. Graph State projects successful signatures, completed call IDs, retrieved evidence IDs/count, Matrix-loaded state, usage counters, and other bounded progress fields. Resume must reject `state_projection_mismatch` rather than choose an unrecorded or duplicated tool execution.
