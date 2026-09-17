# GLM Canary execution-plan v1.2

v1.2 preserves the v1.1 request, budget and no-retry contract while adding an immutable `canary_attempt_id`, task/brief identities, an implementation-commit ancestor binding and a fingerprint of `canary.py` plus `cli.py`. The plan commit may follow the implementation commit: execution accepts that relationship only when the implementation commit is an ancestor of `HEAD` and the current runtime fingerprint is unchanged.

The run ID is deterministic from schema version, provider, request model, task ID, brief ID and attempt ID. This prevents a second Canary from reusing the preserved v1.1 run identity or artifact directory. The plan/example is added only after the implementation support commit is fixed.

`canary_execution_plan.example.json` is immutable attempt 002. `canary_execution_plan.attempt-003.json` is a separate immutable plan bound to the B08R3 implementation; it has a different attempt ID, run ID, and artifact target. Neither plan may be overwritten.
