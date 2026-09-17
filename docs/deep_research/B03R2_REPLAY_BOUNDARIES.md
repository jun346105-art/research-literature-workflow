# B03R2 Replay Boundary Correctness

B03R2 closes the five post-B03R safety-review gaps without changing B01/B02/B03 history. The batch remains offline and internal; Gate A is not authorized by this document.

## Reducer and stream-end finalization

`reduce_runtime_events()` reconstructs only durable facts from any validated event prefix. It never treats the absence of a terminal event as a terminal fact. A checkpoint may therefore end at `operation_reserved`, `operation_dispatched`, `retry_scheduled`, or any other valid event.

`replay_runtime_events()` validates the untrusted checkpoint again, verifies its prefix against the unified stream, reduces the tail, and only then runs stream-end finalization. If a complete stream still ends with a dispatched attempt without a terminal event, the result is `outcome_unknown` plus `ManualInterventionRequired`.

## Unknown budget choice

This batch selects **A: retain reservation; do not create a durable unknown charge**. Unknown is a conservative derived view. A later explicitly authorized reconciliation may replace the reservation with one terminal charge. This avoids both premature unknown charge on a dispatched-prefix checkpoint and duplicate charge when the tail contains success or known failure.

## Retry and replan recovery

Known retryable failure can be resumed by appending the deterministic `retry_scheduled` and next `operation_reserved` facts before dispatch. The operation ID remains stable and the next attempt ID changes. A dispatched prefix is never automatically re-executed and remains unknown at stream end.

Abstain/success facts carry the causal parent for `replan_decided`. If the decision is missing, controlled resume appends that same deterministic decision once, then continues the bounded plan. Repeated resume cannot increment the replan counter twice.

## Public boundary and checkpoint trust

The package root exports the controlled `CrashSafeFakeHarness` and replay/checkpoint types, but not the internal `_OperationInvoker`. Fake Provider/Tool classes remain test fixtures and are not a security boundary. Every checkpoint passed to replay is revalidated from its serialized fields, including model-copy inputs; invalid schema, identity, sequence, head, state, ledger, or journal data fails closed.

## Evidence

`tests/test_deep_research_b03r2.py` covers every valid event-prefix checkpoint, dispatched-prefix success tail, stream-end unknown, retry and replan resume boundaries, checkpoint tamper, public export, and durable reserve/dispatch entry. Existing B03R canonical JSON, fsync, timeout, cancellation, response-lost, CRLF, hash-chain, schema, and replay tests remain required.
