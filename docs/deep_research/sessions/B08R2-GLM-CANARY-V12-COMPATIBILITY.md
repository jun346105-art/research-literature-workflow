# B08R2 GLM Canary v1.2 Compatibility Repair

This bounded compatibility repair starts at `c7841850ea1ef563c3b4f35c694e8a933b1b1eff`. It preserves the failed v1.1 artifact and its `dr-run-dc27b7d035bba74e18f4c7f3` identity unchanged.

v1.1 remains accepted without semantic changes. v1.2 adds `canary_attempt_id`, task/brief identities, `implementation_commit_sha`, and `runtime_source_sha256`. Its run identity is canonical over schema version, provider, model, task, brief and attempt, so attempt `002` deterministically resolves to `dr-run-e195b665d03ebf536d0bc63d`.

The v1.2 implementation commit is `63ef574d699ae29297ab483700c526f4974c22c8`. A plan may be committed after that implementation: preflight requires this commit to be an ancestor of current `HEAD` and requires the current fingerprint of `src/litflow/deep_research/canary.py` plus `src/litflow/cli.py` to equal the immutable plan. This avoids a HEAD-equality cycle while failing closed on relevant source drift.

The only future live command is documented after the plan commit. It still reads a credential only at execute time, makes at most one call with zero retries, and rejects an existing artifact directory before any durable dispatch. This session runs no Provider request and creates no output artifact.
