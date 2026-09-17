# B08E2E-R5 — Planner Output Contract and Non-empty Plan Calibration

Status: `completed` / offline-only; no Key, HTTP or new real E2E.

Attempt-006 remains immutable:

- `runtime.jsonl`: 6,472 bytes, SHA-256 `24f948df9289581057af937e9404ced287ca1aca6fb31d7eb7d150a6b16e48b5`
- `checkpoint.json`: 1,943 bytes, SHA-256 `709ecc5d4514f666c1aae95e5e056041500d36180468078b1308941d63d9b7a2`

The artifact proves a received/parsed/model-verified response with `planner_empty`, actual usage `276/543/819`, cost `0.0008706 CNY`, and zero Tool/Writer calls. It does not retain the original JSON content, so the exact missing/null/empty/alias shape is `not_provable`. Code inspection shows all empty paths converged at B04 `_validate_draft_scope` after `PlannerDraft` normalization.

The Planner prompt now contains a compact exact JSON template and minimum-one-subtask example. `PlannerDraft.subtasks` is Schema-constrained to 1–8 items. Missing/null/empty/alias shapes produce `planner_empty` with non-empty shape/count diagnostics; malformed item fields produce `planner_schema_invalid`; dependency/DAG and explicit permission violations remain separate fail-closed outcomes. The program never fabricates a Subtask.

Attempt-007 is frozen separately at [the attempt-007 plan](../e2e/v1.1/glm_e2e_pilot_plan.attempt-007.json).
