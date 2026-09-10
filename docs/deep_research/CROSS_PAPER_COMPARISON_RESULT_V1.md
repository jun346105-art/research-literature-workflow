# Cross-paper Comparison Attempt-003 Closure

Result: `real_cross_paper_comparison_e2e_pass_under_frozen_source_scoped_corpus`.

Attempt-003 (`glm-5.3-flash-deepresearch-cross-paper-003`, run `dr-run-02a0613ba863c12bf851a58e`) completed once under the immutable [Attempt-003 plan](e2e/v1.2/glm_e2e_cross_paper_plan.attempt-003.json). The run used the frozen local corpus only, one GLM Structured Planner call, four successful local read-only Tool calls, and one GLM Single Writer call. No Web, vision, files, parallelism, fallback, or Multi-Agent path was used.

The source allowlist was applied before BM25 ranking. With 185 corpus passages, the selected source scopes contained 16 L4DLHQUZ candidates and 18 3NLKTSIP candidates; the frozen qrels ranked 11 and 12 respectively, both within bounded `retrieval_top_k=12`. Both target passages were read and admitted as valid EvidenceUnits. The final graph contained exactly the two selected Sources and two EvidenceUnits.

The validated report contained six Claims and eight Citations. Claim `dr-claim-fafc80125d46b92f263995c4` had citations covering both independent Source IDs, so the result is a structural cross-source comparison rather than two unrelated summaries. Quote/span/locator and deterministic grounding validation passed; no gap, conflict, or replan was forced.

Runtime and ledger facts were consistent: 6,123 total tokens (4,561 input / 1,562 output), cost `4011.2` micros, client-observed elapsed `12.4413195s`, two provider calls, four tool calls, zero retries and zero replans. The full replay and checkpoint replay matched and replay performed zero external calls. `author_review_required=true`, `publication_ready=false`, and semantic correctness remains unverified.

The complete file-level hashes are recorded in [the machine-readable manifest](e2e/v1.2/cross_paper_result_manifest.attempt-003.json). Attempt-001, Attempt-002 and Attempt-008 artifacts remain immutable historical evidence. No Key was read and no Provider/API/HTTP call was made during closure.
