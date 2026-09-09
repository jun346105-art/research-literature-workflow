# B08E2E-R4 — Planner Scope Ownership and Diagnostics

Status: `completed` / offline-only; no Key, HTTP or new real E2E.

Attempt-005 remains immutable. Its artifact proved a durable `planner_scope_invalid` failure with actual usage `252/429/681`, cost `0.0007014 CNY`, and zero tool/Writer calls, but its `diagnostics` object was empty. The exact offending field is therefore not recoverable from the artifact; the incident is classified as a program contract/prompt mismatch, not proof of actual model overreach.

The old B04 validator compared model-provided `constraints`, `scope_inclusions` and `scope_exclusions` to the Brief by exact tuple equality. R4 keeps B04’s fail-closed protections but moves ownership to the program at the E2E boundary: the approved Brief supplies formal task/brief/locale/constraint/scope fields; the Planner supplies only local subtask structure and allowed operation intent. Explicit Web, vision, files, write, non-frozen corpus, unknown tool, identity, dependency and DAG violations remain rejected. Omitted formal scope is inherited, not guessed.

Scope failures now record a safe `validation_rule`, `field_location`, `offending_subtask_local_key`, approved constraint IDs, observed type, bounded length and SHA-256. No raw Planner text, reasoning, response envelope, Authorization, key or private path is retained. Attempt-006 is frozen separately with a new attempt/run/artifact identity.
