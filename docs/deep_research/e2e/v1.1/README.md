# Controlled GLM DeepResearch E2E pilot v1.1

This directory contains immutable attempt-002 through attempt-006 plan revisions. Earlier attempts and the original v1 plan remain byte-preserved and are not overwritten. Attempt-006 uses `attempt_id=glm-5.3-flash-deepresearch-e2e-006`, new deterministic run IDs, stage-specific low/high reasoning, 2,048/4,096 Planner input/output and 4,096/4,096 Writer input/output ceilings, and new artifact targets. Its two-call theoretical worst cost is 0.0139264 CNY with a 0.02 CNY hard limit.

The v1.1 schema is generated from `GLME2EPilotAttemptPlan` and adds only the explicit attempt identity needed to keep a repaired implementation binding out of the old v1 plan. It remains a controlled pilot, not a benchmark or a completed real run.
