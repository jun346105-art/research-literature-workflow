# B08E2E-R7 — Writer Identity Ownership

Status: `completed` / offline-only. No credential was read, no Provider/API/HTTP call was made, and calibration-003 was not executed.

## Attempt-002 audit

Calibration-002 (`dr-run-06f51068840bca6b745f6268`) is permanently retained as a known failure. Its `calibration_result.json` SHA-256 is `964FF4275B3A3D25F57ABEA98016F95D9EA12AEF9B1FB90764470A55162E2787`; `runtime.jsonl` is `ACDE359A71E70309628662AC32718633A623C1163867313C7A6830A8BC08FE2F`; `checkpoint.json` is `705F8A0FD3DF880CACEAC4E5E15A5A49E842041D647553BCE65039D37B5575C9`. No file was changed.

The recorded response facts were HTTP 200, parsed JSON, verified model identity, usage reported, `finish_reason=stop`, one section/claim/citation, and `writer_schema_invalid`. The first Pydantic error was `string_too_short` at `brief_id`. The artifact does not prove that any other identity field was valid.

## Root cause

`WRITER_PROMPT` previously required a full `ReportDraft` object and copied `schema_version`, `task_id`, `brief_id`, `plan_id`, and `run_id` into its example. `GLMSingleWriter` then validated the model response directly as formal `ReportDraft`. This incorrectly made model-generated system identity a prerequisite for Writer success.

## Ownership fix

The private `WriterContentDraft` contains only sections, claim/citation suggestions, abstention content and conflict disclosures. It is strict for content fields and ignores harmless metadata. `GLMSingleWriter` strips one JSON fence, parses the object, discards all program-owned identity fields (including nested occurrences), and records only bounded field names in `model_supplied_owned_fields`. `SingleWriterRunner` calls `finalize_writer_content_draft`, which injects trusted `schema_version`, `task_id`, `brief_id`, `plan_id`, and `run_id`; existing Validator logic then creates formal report, claim and citation IDs and preserves evidence/quote grounding.

All Pydantic failures are summarized with `validation_errors_count` and at most 16 `{type, location}` entries. No input values, full response, reasoning, Authorization, Key or private path is persisted.

## Calibration-003

The new immutable plan is [writer_calibration_plan.calibration-003.json](../calibration/v1/writer_calibration_plan.calibration-003.json):

- implementation commit: `90262da09c4b23857ca7ad6aa3b87d0a0f3be199`
- runtime source SHA-256: `ced52128187176fd7e8f59b41e20df215df183525054aa2749f25d0cf12865e1`
- calibration ID: `writer-calibration-003`
- deterministic run ID: `dr-run-ea36f934bb751fb5a0d4885a`
- artifact target: `outputs/deep_research/writer_calibration/v1/dr-calibration-ea36f934bb751fb5a0d4885a`

Dry-run/preflight passed and the target is absent. A real calibration-003 requires separate manual credential injection and authorization.
