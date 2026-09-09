# Controlled GLM DeepResearch E2E pilot v1.1

This directory contains immutable attempt-002 and attempt-003 plan revisions. Attempt-002 is preserved as the failed historical run; the original v1 plan remains byte-preserved and is not overwritten. Attempt-003 uses `attempt_id=glm-5.3-flash-deepresearch-e2e-003`, new deterministic run IDs, and new artifact targets; it retains the same provider, task categories, ordinary-model channel, budget, prompt hashes and local corpus identity.

The v1.1 schema is generated from `GLME2EPilotAttemptPlan` and adds only the explicit attempt identity needed to keep a repaired implementation binding out of the old v1 plan. It remains a controlled pilot, not a benchmark or a completed real run.
