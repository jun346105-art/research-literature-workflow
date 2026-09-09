# Real Single-Paper DeepResearch E2E Result v1

Attempt-008 (`dr-run-8b30915e93a6e6b5ee8137c5`) completed the frozen single-paper local-corpus path with one real GLM Structured Planner call, four local read-only Tool calls, one real GLM Single Writer call, deterministic EvidenceGraph/assessment/Report validation, and a complete terminal.

Status: `real_single_paper_e2e_pass`.

- Planner/Writer/Tool calls: `1 / 1 / 4`; retries `0`; replans `0`.
- Usage: 4,215 input / 1,278 output / 5,493 total tokens; cost `3475.2` micros; elapsed ledger `11.940211900000577` seconds.
- Validated plan: 2 Subtasks; EvidenceGraph: 2 Sources, 2 EvidenceUnits, 6 edges; assessment gaps/conflicts: `0 / 0`.
- Report: `complete`; deterministic grounding `true`; `author_review_required=true`; `publication_ready=false`.
- Full replay and checkpoint replay matched; replay made zero external Provider, Planner, Writer or Tool calls.

The five immutable artifact hashes are recorded in [Attempt-008 artifact manifest](e2e/v1.2/e2e_result_manifest.attempt-008.json). No API Key, Authorization, raw reasoning, or private absolute path was persisted.

This is a scoped real single-paper result against the frozen local corpus. It does not establish semantic correctness, publication quality, Web, multimodal, Multi-Agent, Critic, remote exactly-once, or long-task reliability.
