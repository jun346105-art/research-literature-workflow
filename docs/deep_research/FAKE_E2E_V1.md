# Deterministic Fake E2E v1

The harness in `src/litflow/deep_research/fake_runtime.py` uses pre-registered synthetic steps, `FakeClock`, immutable policy contracts and the B02 state/event kernel. It is a reliability test bench, not a research agent or model-quality benchmark.

| Scenario | Expected terminal | Policy evidence |
| --- | --- | --- |
| `success_minimal` | `complete` | tool + provider success |
| `insufficient_evidence` | `insufficient_evidence` | abstention / grounding rejection |
| `transient_retry_success` | `complete` | one retry, two attempts |
| `timeout_exhausted` | `failed` | bounded timeout retry then `operation_timeout` |
| `cancel_before_next_call` | `failed` | idempotent cancel, no second call |
| `budget_exhausted` | `failed` | pre-dispatch budget rejection |
| `single_replan_success` | `complete` | one admitted changed plan |
| `replan_limit_exceeded` | `insufficient_evidence` | second plan rejected by quota |
| `unknown_non_idempotent_outcome` | `failed` | no blind resume/retry |

Every result exposes policy events, ledger, journal, call count and durable boundary count. Interruption at each boundary returns a snapshot; `resume()` continues from that snapshot. Full and resumed results must have equal terminal state, ledger, journal and call count. `replay_policy_events()` rebuilds local policy facts and makes zero provider/tool calls.

Scenario values and fake costs are synthetic fixtures only; they must not be presented as real provider quality, latency or cost measurements.
