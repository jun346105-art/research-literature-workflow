# B08E2E-R6 — Writer Contract and Development Calibration Channel

Status: `completed` / offline-only; no Key, HTTP or real Writer call.

Implementation commit: `adc04db10d41eb82bc1f1035f12f0d365f0dea51`.
Runtime source SHA-256: `8bd375796790060d057a6cfb26064fb7ecadfe22a2db295977103c3aa8997aa4`.

Attempt-007 remains immutable. Its Writer `writer_draft_invalid` root cause is `not_provable` because the historical artifact had empty Writer diagnostics; code inspection covered JSON, schema, evidence reference, quote and report validation paths.

R6 adds safe Writer error diagnostics, strict JSON-template guidance, deterministic Writer contract validation, and durable `validated_plan.json`, `evidence_graph.json`, and `assessment.json` artifacts referenced by the unified runtime stream through hashes. Resume validates those hashes and does not repeat local tools. Planner subtasks now carry only the bounded `research_action` enum; compose/write/report actions are rejected before execution.

The Writer-only development channel is frozen separately at [writer_calibration_plan.json](../calibration/v1/writer_calibration_plan.json), with `calibration_id=writer-calibration-001`, one Provider-call budget, zero retries, and a new artifact target. It is a development calibration, not a formal E2E or benchmark result. Only dry-run/preflight was executed.

Attempt-007 artifact remains immutable. Read-only hashes are `runtime.jsonl=23D163B105ED8222A3D869BAB53353CD9EF94B2928A996745C06176104263DE1` and `checkpoint.json=F3FA39A377A1C290704DB1AB46CBFE8BFA54243652D0572ABB9A9C1AF3BC9944`. The historical `writer_draft_invalid` cause remains `not_provable`; the artifact contained no Writer diagnostics.

The calibration target is `outputs/deep_research/writer_calibration/v1/dr-calibration-76017a7df7b64fc2dcad8730` and does not exist. Preflight validates the implementation ancestor, source fingerprint and exact target without reading credentials or creating output.
