# Local Research Executor and Evidence Graph v1

B05 / S13–S14 adds an offline-only, single-executor chain:

```text
approved Brief -> ValidatedResearchPlan -> read-only local tools -> EvidenceUnit -> EvidenceGraph
```

`LocalResearchExecutor` accepts only a B04 plan whose task, brief and immutable approval identities match. It walks the program-owned stable topological order. Missing approval, a mismatched plan, or an unsatisfied dependency fails before a tool call.

The only registry capabilities are `search_local_corpus` (frozen BM25 passages) and `read_passage` (a known passage ID). They are sequential, read-only and idempotent. They do not accept arbitrary file paths, Web queries, providers, shell commands or write operations. Tool attempts use the existing B03R2 reserve -> durable dispatch -> terminal-event protocol and replay uses `replay_runtime_events()` without tool invocation. The executor does not alter B03R2 reducer, finalizer, checkpoint or unknown-outcome semantics.

`EvidenceCandidate` is an untrusted passage/quote proposal. The program maps it through the existing strict span mapper, creates the final `EvidenceUnit` ID and retains chunk/page/span/hash provenance. A missing, ambiguous or cross-passage anchor is rejected; no model/Fake selector may create an Evidence ID. The minimal graph has program-owned `ResearchSubtask`, `Source` and `EvidenceUnit` nodes, with only `subtask_retrieved_source`, `source_contains_evidence` and `evidence_supports_subtask` edges. Nodes and edges are canonical, edge endpoints and run identity are validated, and duplicate/self/cross-run edges fail closed.

Schemas in [executor/v1](executor/v1/README.md) are canonical UTF-8/LF exports. This remains `internal_result`: no real Planner/Provider, Web, PDF tool, Writer, Claim/Citation generation, final report, replan, Multi-Agent, Critic or formal output artifact is implemented.
