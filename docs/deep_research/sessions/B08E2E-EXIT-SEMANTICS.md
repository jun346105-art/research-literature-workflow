# B08E2E Exit Semantics Repair

Status: `completed` / offline-only; no Key, HTTP, Provider, retry or real E2E execution.

Planner and Writer unknown outcomes now use structured error codes/types. Planner `outcome_unknown` persists `operation_unknown` and a checkpoint, does not invoke Writer or retry, and reaches CLI exit code `3`. Writer unknown becomes `manual_review_required` with the same exit code. Known contract/configuration failures remain exit code `2`; complete remains `0`. Replay is unchanged and invokes no Provider.

The repair changes the E2E source fingerprint, so the original v1 pilot plan and its run/artifact identities remain untouched. Attempt-002 is frozen separately under `e2e/v1.1/` with a new `attempt_id`, run IDs and artifact targets.
