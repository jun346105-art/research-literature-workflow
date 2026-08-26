# Reference Pattern Decisions

Each decision is evidence-bound and is not an implementation authorization. Admission gates must pass before a deferred or conditional item joins the default path.

| Pattern | Observed problem / current evidence | Decision | Admission gate | Default path |
| --- | --- | --- | --- | --- |
| LangGraph Single-Agent orchestration | M8 has a StateGraph, policy gates, HITL and fake coverage; real AG01 grounded answer failed | `reuse_or_wrap_now` | Kernel owns evidence identity and validator; Fake cases pass | yes, adapter only |
| Explicit lifecycle state | M8 needs bounded calls, terminal outcomes and resume projection | `adopt_now` | S07 transition guards reject illegal transitions | yes |
| Append-only durable events/replay | M8 v2 fake canonical replay and hash-chain validation passed | `reuse_or_wrap_now` | new event contract passes corruption/projection/replay tests | yes |
| Research Brief approval | open research scope must not trigger unapproved real work | `adopt_now` | unapproved Brief cannot execute | yes |
| Evidence Gap and bounded replan | M8/QA safe failures show gaps must remain visible | `adopt_now` | finite replan, token/tool/time limits and duplicate detection | yes |
| Single Writer | existing writing is evidence-record bound and author-review gated | `adopt_now` | Writer receives validated packets only | yes |
| asyncio + Semaphore | no observed parallel bottleneck or provider-rate evidence | `defer_until_evidence` | measurable independent tasks plus budget-safe cancellation tests | no |
| Supervisor + Research Workers | no Single-Agent held-out baseline or equal-budget gain | `conditional_experiment` | S47 gate and pre-registered equal-budget ablation | no |
| Red–Blue / Critic | no real DR error taxonomy or net-repair evidence | `defer_until_evidence` | taxonomy from failures, whitelist patches and convergence metric | no |
| L1/L2/L3 context compression | no measured recall/token trade-off | `defer_until_evidence` | S36 recall at least 95% and token reduction at least 30% | no |
| Cross-Agent shared memory | evidence identity must not be replaced by conversational memory | `reject_for_default_path` | none; use shared Evidence Store instead | no |
| SQLite / vector memory | JSON/JSONL and file-backed MVP jobs exist; no persistence pressure proven | `defer_until_evidence` | S39/S44 evidence that file contracts fail recovery/concurrency needs | no |
| Multi-provider hot switching | one transport path and validator equivalence are not yet frozen | `defer_until_evidence` | provider transport contract proves validator cannot be bypassed | no |
| page+bbox multimodal evidence | A03 has text/page provenance but no regions; this is desired differentiation | `conditional_experiment` | S42–S47 contracts, region grounding and text-only held-out comparison | no |

The observed M8 failure is a reason for evidence-kernel ownership and safe termination, not evidence for more roles, concurrent workers, memory, or self-critique.
