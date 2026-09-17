# ADR-002: Experiment and Data Governance

- Status: Accepted
- Date: 2026-08-26
- Scope: DR-S03/DR-S04 governance freeze

## Decision

Separate fake, canary, dev, held-out and public-benchmark strata. Freeze run identity, append-only artifact expectations, budget/termination accounting, metric categories and external-call approval gates before any real call. Record failures rather than overwrite them.

Real LLM requires Gate A and explicit user budget/provider authorization; Web requires Gate B; held-out requires immutable inputs/config/thresholds. Multimodal, Multi-Agent and Critic require pre-registered controls and positive retention evidence.

## Consequences

M8 remains `experimental_partial_pass`: fake durable evidence and a real planning/tool chain do not establish grounded completion after `evidence_anchor_not_found`. New experiments cannot cite that result as production readiness. This ADR adds governance only, no data, run, provider or output.
