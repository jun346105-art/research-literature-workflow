# B03R Unified Runtime v2

B03R repairs the B03 offline execution boundary with one ordered, append-only runtime stream. It is an internal reliability result and does not authorize any real provider, model, network, or production-output path.

## Authoritative stream

`src/litflow/deep_research/runtime_v2.py` defines `RuntimeEventEnvelope` and `UnifiedEventStore`. Every event has one run ID, stream sequence, causal operation/attempt IDs, previous hash, and a hash over the semantic envelope without `event_hash` itself. `canonical_json_bytes()` is the only hash serializer: UTF-8, sorted keys, compact separators, non-ASCII preserved, NaN/Infinity rejected, UTC datetimes normalized, Decimal rendered as fixed strings, and enum values reduced to stable values. JSONL line endings are transport only and are never hash input.

The stream records `operation_reserved` before `operation_dispatched`. A durable dispatch without a terminal outcome is replayed as `outcome_unknown` and returns `ManualInterventionRequired`. Replay is pure: it rebuilds run state, operation journal, and budget ledger without Provider/Tool calls, external status lookup, retry, replan, compensation, or final-answer generation.

## Budget and resume rules

The selected unknown policy is **A: retain the reservation and do not create a durable unknown charge**. A response-lost or stream-end unknown therefore remains a conservative reservation-only view; an explicitly authorized future reconciliation may replace that reservation with one terminal charge. Succeeded and known-failed attempts reconcile once; repeated replay or resume cannot create a second charge or a second external call. Retry is finite and allowlisted; every retry uses the same operation ID and a new attempt ID. Non-idempotent side effects never receive blind retry after an unknown outcome.

Effective operation timeout is `min(configured operation timeout, remaining run deadline)`. `FakeClock` records latency and deterministic backoff. Cancellation is idempotent and only prevents later dispatch; it does not claim to cancel a request already dispatched remotely.

## Coordinated checkpoint

`CoordinatedCheckpointV2` stores the unified stream sequence/head and hashes of `RunState`, `BudgetLedger`, and `OperationJournal`. Resume verifies the checkpoint prefix against the same stream before replaying the tail. Tampered sequence, previous hash, payload, duplicate, cross-run, unsupported event, or checkpoint content fails closed.

## Explicit non-guarantees

The local runtime cannot guarantee exactly-once execution of a real remote request. A request that may have completed while its response was lost is recorded as unknown. Request-status lookup or provider idempotency-key reconciliation, if ever approved, must be a separate explicit workflow. This batch contains only scripted Fake Provider/Tool scenarios and must not be used to claim real Agent or model capability.

## Evidence

See `tests/test_deep_research_b03r.py` for crash windows, response-lost replay, zero-call replay, conservative reservation handling, canonical serialization, schema roundtrip, CRLF transport, checkpoint-tail replay, tamper rejection, timeout/deadline, cancellation, retry, and lifecycle ordering.
