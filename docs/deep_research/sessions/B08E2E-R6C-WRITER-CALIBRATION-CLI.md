# B08E2E-R6C — Writer Calibration CLI Wiring

Status: `completed` / offline-only. No credential was read, no Provider/API/HTTP call was made, and no real Writer calibration was run.

## Root cause

`writer_calibration_cli.py` previously accepted only `--dry-run`. The existing `WriterCalibrationRunner` and GLM Writer adapter were present, but the CLI never instantiated them, never entered an execution branch, and never wrote a calibration result artifact. Omitting `--dry-run` therefore still performed only preflight, while `--execute` was rejected by argparse.

## Contract

The CLI now requires exactly one explicit mode: `--dry-run` or `--execute`. Dry-run performs read-only preflight and creates no artifact. Execute validates the frozen plan and unique target, then reads the credential only at the explicit execution boundary, invokes the existing `WriterCalibrationRunner` once, and writes `runtime.jsonl`, `checkpoint.json`, and a redacted `calibration_result.json`. Planner and Tool calls are structurally absent; retries remain zero. Complete maps to exit 0, known/contract failure to 2, and unknown/manual intervention to 3.

## Plans

`writer-calibration-001` is retained unchanged as historical `preflight_passed / real_execute_not_run`; it is not relabeled as an executed calibration. The new immutable plan is [writer_calibration_plan.calibration-002.json](../calibration/v1/writer_calibration_plan.calibration-002.json):

- implementation commit: `e8b12789cc747359808a351e70f5c4861edb4163`
- runtime source SHA-256: `84d1a54b7d775aca38cf831589694aa91313d6712fc707151677470cfff9ee8d`
- calibration ID: `writer-calibration-002`
- deterministic run ID: `dr-run-06f51068840bca6b745f6268`
- artifact target: `outputs/deep_research/writer_calibration/v1/dr-calibration-06f51068840bca6b745f6268`

The calibration target is required to be absent before execution. Only dry-run/preflight and offline mock/network-deny tests have been run for this batch.
