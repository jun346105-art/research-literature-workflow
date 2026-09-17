# Offline Single-Agent E2E v1

Status: `internal_result`.

The minimum offline chain is:

```text
approved Brief -> validated Plan -> local read-only Executor -> EvidenceGraph
-> B06 gap/conflict assessment -> at most one bounded replan -> FakeWriter Draft
-> deterministic Report Validator
```

`tests/test_deep_research_single_writer.py` exercises complete, partial, insufficient-evidence, and manual-review outcomes; fake/cross-run Evidence, absent citations, ungrounded quotes, missing provenance edges, duplicate Claim/Citation proposals, untrusted graph mutation, harmless extra draft metadata, malformed drafts, cancellation, deadline, budget, unknown outcomes, reserve/dispatch fsync failure, terminal-event/checkpoint recovery, full replay, checkpoint-plus-tail replay, and one legal replan followed by a second-replan block.

Replay is pure: it invokes no Planner, Executor, Assessor, Writer, tool, API, or Provider and cannot create duplicate Claims/Citations or charges. All test event/checkpoint files remain under pytest temporary directories. The batch creates no formal report output and demonstrates neither a real DeepResearch Agent nor real GLM, Web, tool, multimodal, Multi-Agent, or Critic behavior.
