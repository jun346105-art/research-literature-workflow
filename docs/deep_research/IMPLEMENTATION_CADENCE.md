# Compressed Implementation Cadence

The logical IDs remain authoritative. Batches reduce planning overhead only; no high-risk Gate, real call, held-out run or destructive action is merged into an ordinary coding batch.

| Batch | Logical sessions | Scope |
| --- | --- | --- |
| B01 | S05–S06 | Task/Brief/Subtask and Source/Evidence/Claim/Citation contracts |
| B02 | S07–S08 | state, transition guards, durable events/replay |
| B03 | S09–S10 | budget/timeout/cancel/retry and Fake E2E |
| B04 | S11–S12 | Brief approval and Planner |
| B05 | S13–S14 | local Research Executor and Evidence Graph |
| B06 | S15–S16 | Gap/Conflict and bounded replan |
| B07 | S17–S18 | Single Writer and Report Validator |
| B08 | S19 | real canary, separately gated |
| B09 | S20 | failure audit and one hardening pass |
| B10–B11 | S21–S25 | Web adapters, quality policy and Web canary |
| B12–B14 | S26–S32 | benchmark, metrics, dev and held-out |
| B15–B18 | S33–S41 | context, API, persistence and Docker/CI |
| B19–B21 | S42–S47 | multimodal contracts, VLM and ablation |
| Optional | S48–S57 | Multi-Agent/Critic only after gates |
| Release | S58–S63 | public benchmark, safety and release |

B01 is the next eligible batch. It defines contracts only; it does not implement a provider, state machine, output run, or external experiment.
