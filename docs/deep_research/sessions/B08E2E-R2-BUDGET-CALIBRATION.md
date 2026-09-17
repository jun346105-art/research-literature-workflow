# B08E2E-R2 — GLM Structured Generation Budget and Usage Calibration

Status: `completed` / offline-only; no Key, HTTP or new real E2E.

Attempt-003 remains immutable:

- `runtime.jsonl`: 6,360 bytes, SHA-256 `9d4e85eea2ed061b37f361ed8e0a3a2ce1d82b22183290cf56a9624f5636cae8`
- `checkpoint.json`: 1,933 bytes, SHA-256 `1e65624150cb2a969ab495e91e1098bb5d83367f52aa6e6c20f34ea48d11b281`

The artifact proves HTTP 200, parsed response, verified model and reported usage, but the Planner content was empty with `finish_reason=length`. It does not prove server-side billing was zero. The repair preserves this artifact and adds actual usage/cost reconciliation on future application failures.

## Offline measurements

- Minimal PlannerDraft: 459 UTF-8 JSON characters.
- Representative two-subtask PlannerDraft: 619 characters.
- Single-paper Planner prompt: 609 characters.
- Single-paper Evidence View plus assessment Writer prompt: 2,787 characters.
- Minimal ReportDraft: 464 characters.
- Representative four-claim/two-section ReportDraft: 1,301 characters.

The conservative attempt-004 policy uses 1,024 input and 1,024 output tokens per Planner/Writer call. The 1,024 input ceiling covers the measured Writer prompt under a conservative 4-character/token estimate; output 1,024 leaves room for reasoning plus a structured draft. Thinking remains `enabled` with `reasoning_effort=max` because the existing GLM contract does not confirm a safe disabled-thinking value; the output budget, not an unverified parameter, is calibrated.

Worst-case cost at two calls and the frozen 0.4/1.4 CNY per-million input/output rates is:

`2 × (1024 × 0.4 + 1024 × 1.4) / 1,000,000 = 0.0036864 CNY`.

The hard limit remains `0.01 CNY`, or approximately 171% of this theoretical worst case (about 171% total-cost coverage, well above the required 20–30% safety margin). Actual provider usage and cost are reconciled by attempt ID; reservation maxima are never recorded as observed usage.

Client-observed elapsed time is now recorded via monotonic clock on Planner and Writer success, known-failure and unknown paths. It is not a claim about server-side duration.

Attempt-004 is frozen separately at [the attempt-004 plan](../e2e/v1.1/glm_e2e_pilot_plan.attempt-004.json).
