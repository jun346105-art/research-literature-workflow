# Controlled single-paper GLM DeepResearch E2E Attempt-008

`glm_e2e_pilot_plan.attempt-008.json` freezes one `single_paper` task against the immutable local `outputs/rag_bm25_v1/passages.jsonl` corpus. It binds the current implementation/source fingerprint and Planner/Writer prompt hashes, keeps the stage-specific low/high reasoning budgets, allows two Provider calls with zero retries and one bounded replan, and disables Web, vision, files, tools, parallelism and fallback.

The plan is a manual-execution candidate only. Its artifact target is versioned and currently absent. `preflight_e2e_pilot()` verifies plan, corpus, prompt, implementation and artifact identity without reading credentials or sending HTTP.

The complete path is approved Brief → real structured Planner → local read-only Executor → EvidenceGraph → deterministic gap/conflict assessment → real Single Writer → deterministic Report Validator → terminal result. No Attempt-008 request has been executed by this agent.

The plan freezes one Provider call for Planner and one for Writer (`max_provider_calls=2`, `max_provider_attempts=2`, `max_retries=0`, `max_replans=1`), 60-second operation timeout, 180-second run timeout and 0.02 CNY hard limit. CLI exit semantics remain complete=0, known failure=2 and unknown/manual intervention=3.

The cross-paper follow-up is frozen separately in [Attempt-003](glm_e2e_cross_paper_plan.attempt-003.json) after source-scoped BM25 stabilization. It is a two-source, local-only, dry-run/preflight-ready plan with bounded `retrieval_top_k=12`; Attempt-001 and Attempt-002 remain immutable historical failures, and no Attempt-003 request has been executed.
