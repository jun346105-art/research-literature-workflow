# ADR-000: Evolve LitFlow as an Evidence-First DeepResearch Track

- Status: Accepted
- Date: 2026-08-26
- Scope: DR-S00 governance only

## Context

LitFlow already has a frozen v1.0 MVP, historical evidence artifacts and a documented M8 experimental Agent result. A new research capability must preserve those facts, including safe failures, rather than copy a generic Agent demo or retrofit unverified claims into MVP history.

## Decision

1. Evolve LitFlow on an independent DeepResearch milestone branch instead of rewriting or replacing the MVP.
2. Build a reliable Single-Agent baseline before considering Multi-Agent orchestration.
3. Use an Evidence-First design: the program, not the model, owns source identity, evidence identity, original spans, validation and final display authority.
4. Treat page/region-aware multimodal engineering-paper evidence as the main planned differentiation from a generic text-only DeepResearch system.
5. Treat Multi-Agent and Critic structures as conditional experiments only. They may remain only after pre-registered, held-out, equal-model/equal-data/equal-budget ablations demonstrate clear net benefit with no grounding-safety regression.

## Consequences

- DR-S00 changes documentation and governance only; it adds no runtime, provider, Web, database, schema, validator, retriever or UI capability.
- M8 retains the honest status `experimental_partial_pass`; its AG01 quote-grounding failure remains part of the baseline.
- Future Sessions must use independent, versioned contracts and artifact paths without modifying old outputs or the MVP tag.
- A negative Multi-Agent or Critic result is retained as an experimental finding and does not become a default product dependency.

## Alternatives rejected

- **Rewrite LitFlow as a new generic Agent demo:** rejected because it would obscure proven MVP boundaries and historical failure evidence.
- **Start with Multi-Agent or Critic orchestration:** rejected because no equal-budget evidence yet establishes a benefit over a reliable Single-Agent baseline.
- **Relax validators to improve apparent completion:** rejected because evidence grounding and fail-closed behavior are protected safety properties.
