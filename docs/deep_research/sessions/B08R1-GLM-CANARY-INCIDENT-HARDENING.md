# B08R1 GLM Canary Incident Hardening

This is the single offline hardening pass after the first B08/S19 Canary artifact. It is not a second Canary, Provider retry, or evidence of a successful remote call.

## Fixed incident facts

The immutable artifact is `outputs/deep_research/canary/v1/dr-run-dc27b7d035bba74e18f4c7f3`. Before this repair, SHA-256 was recorded as:

- `immutable_plan.json`: `5F5A9638EAAB599CB94754038A44101EBBE45A80F01EC7AE07E1A2DB7B9238DF`
- `runtime.jsonl`: `F00E925423C0AFD5946183AC93E185025EE498387E3E2F2C6498901EC5769F00`
- `structured_result.json`: `CA37B3CDDB66F98366D6789713461350992ADC528E1FC7CCFD1ACBE4C6D2669D`

It contains `operation_dispatched` followed by `operation_failed` with `error_code=contract_invalid`, zero reported usage/cost, and an empty provider request ID. The event stream proves a durable dispatch intent, but does not prove that `urllib.request.urlopen()` entered or that the remote service executed the request. That fact remains `not_provable` from the preserved artifact.

## Root cause and minimal repair

The adapter previously collapsed malformed bodies, missing choices/content, model mismatch, application JSON failure, missing usage and inconsistent usage into `contract_invalid` without a safe field-level diagnosis. The CLI also returned zero after every structured result, including `terminal=failed`.

The repair keeps B03R2 ordering, replay and unknown-outcome semantics intact. It adds a redacted `provider_audit` payload plus `adapter_diagnostics.json`, separating:

1. Transport contract: response receipt, HTTP status and JSON body parsing.
2. Provider adapter contract: error envelope, content normalization, exact model identity and usage audit.
3. Application contract: the fixed synthetic response JSON.

`model_identity_unverified` may preserve a received/parsed content fact, but cannot complete the no-fallback Canary. Missing usage reports `cost_verification=unavailable`; inconsistent usage reports `cost_verification=failed`; both keep `cost_audit_complete=false` and cannot complete this plan. No body, Authorization header, credential value, or private path is persisted.

The CLI now returns `0` only for `terminal=complete`, `2` for a known failed terminal, and `3` for `unknown_outcome`/manual intervention. Replay remains pure and does not invoke a Provider or add charges.

## Boundary and disposition

This change prepares a future new versioned plan/run/artifact only. It does not alter the original artifact, create a new artifact, read `ZHIPUAI_API_KEY`, send HTTP, retry, or authorize a second Canary. Completion state after code review is `pending_B08R1_read_only_reaudit`; resume/CV status remains `not_ready`.
