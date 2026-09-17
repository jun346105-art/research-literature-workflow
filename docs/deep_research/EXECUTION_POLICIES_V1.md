# DeepResearch Execution Policies v1

B03 adds an offline policy layer on top of the B02 lifecycle kernel. Policy facts use a separate `PolicyEvent` chain so existing `RunEvent` identities and runtime-v1 replay semantics remain unchanged.

## Error taxonomy

`ErrorCode` is an enum, not a string-matching convention. Each code has fixed retryability, call-accounting and replan semantics in `errors.py`. Contract, grounding, cancellation, budget and invariant errors are never automatically retried. `unknown_outcome` is fail-closed, especially for non-idempotent side effects.

## Budgets and ledger

`BudgetSpec` is immutable and fixed before execution. It bounds provider/tool attempts and calls, input/output/total tokens, retries, replans, optional integer micro-costs, run timeout and operation timeout.

`BudgetLedger` is immutable and monotonic. A call follows `reserve -> dispatch -> reconcile/charge`; reservation checks happen before dispatch. Charges are keyed by operation and attempt identity, so replaying an identical charge is idempotent and conflicting duplicates are rejected. Failed and timed-out dispatched attempts consume calls and observed usage.

## Deadline, cancellation and retry

The runtime injects a monotonic `Clock`; Fake E2E uses `FakeClock` and never sleeps in real time. Operation timeout is bounded by remaining run time. Cancellation is an idempotent signal checked before dispatch, after attempts, before backoff/replan and before terminalization. `RetryPolicy` has finite attempts, an explicit error allowlist and deterministic backoff without random jitter. Every retry gets a new attempt ID.

## Controlled replan and journal

`ReplanPolicy` admits only a changed plan identity and an ordinal below `max_replans`. Replan consumes ledger quota and cannot reset retries, tokens, cost or deadline. `OperationJournal` distinguishes planned, started, succeeded, known failure, unknown outcome and cancelled-before-dispatch. A committed success is not re-executed on resume. An unknown non-idempotent outcome is `manual_review_required`.

Policy events are append-only UTF-8/LF JSONL with fsync, continuous sequence and SHA-256 hash chain. Replay rebuilds ledger and journal without invoking a provider, tool or clock. Local logs cannot prove exactly-once behavior of a remote request after a connection failure.

## Boundary

This is an `internal_result`. It contains no real provider adapter, API key access, LangGraph graph, Web/PDF integration, Planner, Writer, Critic, Multi-Agent execution or production output. Gate A may be requested for review after this offline evidence, but no real call is authorized by B03.
