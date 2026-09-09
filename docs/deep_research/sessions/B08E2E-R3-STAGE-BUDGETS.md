# B08E2E-R3 — Stage-specific GLM reasoning and budgets

Status: `completed` / offline-only; no Key, HTTP or real E2E.

Attempt-004 remains immutable:

- `runtime.jsonl`: 6,903 bytes, SHA-256 `22e9d3225b434401a47ff7fd6b02df05c31826186111df554fbf78dc19611a5f`
- `checkpoint.json`: 1,974 bytes, SHA-256 `023901305b8bddd3cef79321e34e306363ad660e15a8ab7e64451fd12bd03655`

Attempt-004 proves Planner truncation at output 1,024 with `finish_reason=length`, actual usage 252/1024/1276 and cost `0.0015344 CNY`. It is not retried or overwritten.

Attempt-005 uses one shared GLM transport with stage-specific policy:

- Planner: `thinking.type=enabled`, `reasoning_effort=low`, 2,048 input / 4,096 output;
- Writer: `thinking.type=enabled`, `reasoning_effort=high`, 4,096 input / 4,096 output;
- global: two Provider calls, two attempts, zero retries, `max_replans=1`, operation timeout 60s, run timeout 180s, hard limit `0.02 CNY`.

Theoretical worst cost is:

`(2048 × 0.4 + 4096 × 1.4 + 4096 × 0.4 + 4096 × 1.4) / 1,000,000 = 0.0139264 CNY`.

The 0.02-CNY hard limit provides approximately 43.6% safety margin over that worst case. It is a circuit breaker, not a spending target. Actual usage/cost is reconciled by attempt ID; replay cannot charge twice. Stage reservations use the shared BudgetLedger and reject a third Provider call before dispatch.

The new immutable plan is [Attempt-005](../e2e/v1.1/glm_e2e_pilot_plan.attempt-005.json); only dry-run/preflight was executed.
