# ADR-001: Runtime and Evidence Boundaries

- Status: Accepted
- Date: 2026-08-26
- Scope: DR-S03/DR-S04 architecture freeze

## Decision

Evolve DeepResearch in a new `src/litflow/deep_research/` namespace and separate it from frozen MVP/M8 through adapters. Freeze four layers: Domain Contracts, Deterministic Kernel, LangGraph Orchestration Adapter, and Provider/Tool Adapters. LangGraph schedules nodes and integrates checkpoints; it does not own evidence identity, grounding validation or final display.

The program owns Source/Evidence/Claim/Citation identity, provenance and publication authority. The Evidence Store is durable truth; a Model Context View is a bounded derivative. The default is a Single-Agent research executor, bounded replan, Single Writer and deterministic validator. Multi-Agent can only conditionally replace the research executor after evidence.

## Consequences

Existing BM25, qrels checks, span mapper, QA validation and durable events are reuse/wrap candidates, not already integrated DR modules. Initial persistence remains versioned JSON/JSONL and append-only events; SQLite is deferred. No runtime or schema is introduced by this ADR.
