# Durable Runtime Kernel v1

## Lifecycle and guards

`brief_pending → brief_approved → researching → validating → complete` is the happy path. Research may instead end `insufficient_evidence` or `failed`; approved may fail. All three terminal states are absorbing. Approval is read from the B01 brief reference, not a caller-provided bare boolean. B02 intentionally has no timeout, retry, cancel, budget, replan, Planner, Writer or executor state.

## Events, checkpoint and replay

Every valid transition is validated in memory first, then creates one immutable event with continuous sequence, explicit genesis hash, canonical payload SHA-256 and program-generated ID. Audit time does not affect identity. Hashes detect consistency/tampering; they are not signatures or access control.

JSONL append uses UTF-8/LF, validates the full prior prefix, flushes/fsyncs the event, and rejects bad JSON, partial final lines, duplicates, gaps, disorder, cross-run events or chain mismatch. Checkpoints are derived state snapshots with state hash, run/sequence/head checks and same-directory atomic replace. Write order is transition validation → event append → checkpoint; checkpoint failure leaves the event log authoritative. This is single-writer crash recovery, not multi-file ACID or multi-process safety.

Replay validates every event again. It supports empty/full/prefix streams and verified checkpoint plus tail; it emits no new events and calls no external system. B02 is isolated from old M8 code: it borrows only proven ideas such as hash-chain verification and fail-closed replay, while retaining no M8 schema, trace or success claim.

## Deferred work

S09/S10 own budget, timeout, retry, cancel, controlled replan and Fake E2E policies. LangGraph orchestration and provider/tool calls remain later adapters.
