# B08R3 — GLM Canary Application Contract Calibration

## Scope

This offline repair replaces whole-object acknowledgement equality with a private, strict Pydantic v2 acknowledgement contract. It requires `status="ok"`, `provider="zhipu_bigmodel"`, and `model="glm-5.3-flash"`; harmless extra fields are ignored.

## Preserved boundaries

- Transport, provider-adapter, model-identity, usage/cost, budget, WAL/fsync, replay, unknown-outcome, and CLI exit semantics are unchanged.
- Application failures retain already-confirmed transport/provider facts and are recorded as `application_contract` failures.
- Diagnostics persist only error type/location, allowlisted shape, content length, and content SHA-256. They never persist acknowledgement values, raw provider bodies, Authorization, or credentials.
- No credential read, HTTP call, or Canary execution occurs in this repair.

## Attempt 003 freeze

Attempt 002 remains immutable and source-fingerprint-bound to its implementation. Attempt 003 is separately frozen in `../canary/v1.2/canary_execution_plan.attempt-003.json`, with `canary_attempt_id=glm-5.3-flash-text-canary-003`, a new deterministic run ID, a distinct artifact directory, and a binding to the B08R3 implementation commit/source fingerprint. This is design-only: no credential was read and no Canary was executed.
