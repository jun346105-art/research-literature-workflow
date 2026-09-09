# Controlled GLM DeepResearch E2E pilot v1.1

This directory contains immutable attempt-002, attempt-003 and attempt-004 plan revisions. Attempt-002 and attempt-003 are preserved historical runs; the original v1 plan remains byte-preserved and is not overwritten. Attempt-004 uses `attempt_id=glm-5.3-flash-deepresearch-e2e-004`, new deterministic run IDs, 1,024/1,024 Planner/Writer token ceilings, and new artifact targets; it retains the same provider, task categories, ordinary-model channel, prompt hashes and local corpus identity. Its two-call theoretical worst cost is 0.0036864 CNY with a 0.01 CNY hard limit.

The v1.1 schema is generated from `GLME2EPilotAttemptPlan` and adds only the explicit attempt identity needed to keep a repaired implementation binding out of the old v1 plan. It remains a controlled pilot, not a benchmark or a completed real run.
