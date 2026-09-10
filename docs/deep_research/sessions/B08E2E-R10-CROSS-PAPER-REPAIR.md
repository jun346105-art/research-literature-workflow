# B08E2E-R10 — Cross-paper Stabilization and Attempt-003 Freeze

Status: `completed` / `design_only`; final state `ready_for_cross_paper_attempt003_manual_execute`. No Key was read, no HTTP was sent, and Attempt-003 was not executed.

Attempt-001 (`dr-run-8e3c2028b68e14c88fc7b17e`) remains permanently retained as `failed_known / cross_paper_comparison_invalid`. Its runtime SHA-256 is `FC34EE6F305173A2B29552D809B6DEB9FC8F44554D9621D555CE827273407DC9`, checkpoint SHA-256 is `7F6EBFA8CC949903C58728AB0CAA4EA413315BA1E8B8986E5CF7E72CB1626050`, and its plan/artifact were not modified.

The failure occurred after one successful Planner Provider call and one successful local search Tool call, at selected-source Evidence admission. The unbounded full-corpus Top-1 was Q55RU9N6 rather than the plan-selected source, so no read_passage was dispatched. Attempt-002 remains immutable `failed_known / selected_source_evidence_missing`; its Tool success is not rewritten as a Tool failure.

## Repair

The LocalResearchExecutor now accepts optional program-owned source/passage allowlists and per-subtask source routing. Cross-paper CLI execution pre-filters the corpus by selected Source before BM25, applies bounded `retrieval_top_k=12`, then reads and validates only selected passages. A deterministic Writer gate requires at least one Claim whose Citation suggestions cover two distinct Source IDs, without merging unrelated single-source Claims or manufacturing a comparison. Cross-specific Planner and Writer prompts identify the selected sources and require comparison rather than separate summaries. Runtime reducer, checkpoint, replay, budget and retry semantics are unchanged. Known stage/business failures use a shared terminalization helper: successful Tool events remain succeeded, a bounded stage-failure fact plus failed lifecycle is persisted, elapsed is recorded, and the final coordinated checkpoint covers the complete stream head.

## Attempt-002

The new immutable plan is [glm_e2e_cross_paper_plan.attempt-002.json](../e2e/v1.2/glm_e2e_cross_paper_plan.attempt-002.json):

- attempt: `glm-5.3-flash-deepresearch-cross-paper-002`
- run: `dr-run-b966de61dabf031cbfa96d3e`
- artifact: `outputs/deep_research/e2e/v1.2/dr-run-b966de61dabf031cbfa96d3e` (retained `failed_known / selected_source_evidence_missing`; not modified)
- historical implementation commit: `265470ce7ec7bdc70f41df29037e55c896b1c65a`; historical runtime source SHA-256: `b133c7ddd00ff9d53ced077ace11300e7f51e04649b35417061a011d4a9ff23a`
- historical task input SHA-256: `4315f8de67e0cfd65c1e9ce4a296bb6fb6a08cf0652483627417df2a537bfe0e`
- selected source keys: `L4DLHQUZ`, `3NLKTSIP`

Offline cross-paper tests cover selected-source enforcement, source-prefilter-before-BM25, bounded qrel retrieval, missing-source fail-closed behavior, source-specific Evidence, two-source comparison Claim requirements, replay safety, and artifact uniqueness. Attempt-002 remains immutable historical evidence.

## Attempt-003

The stabilized immutable plan is [glm_e2e_cross_paper_plan.attempt-003.json](../e2e/v1.2/glm_e2e_cross_paper_plan.attempt-003.json):

- attempt: `glm-5.3-flash-deepresearch-cross-paper-003`
- run: `dr-run-02a0613ba863c12bf851a58e`
- artifact target: `outputs/deep_research/e2e/v1.2/dr-run-02a0613ba863c12bf851a58e` (absent)
- implementation commit: `0b78a9375133c4ce9350c528ea208416f66fbafd`
- runtime source SHA-256: `45ec8551698385ee218eac2a9adf74fa624b41a0efa7d2b7e8cbfa45a7da3287`
- Planner/Writer prompt SHA-256: `ed51df7a0c3223abbe20d1b0386c6bba5665437f7cb1490977e5f4e3704ca5f9` / `caa0cffb9495863b95ae1e6e9e0945797b5776c727830093d7568fe6cf957445`
- task input SHA-256: `d4dc75dd908f9fdbb4eca65c06dfe4d4c077aab711ee21a2c8f3f638238f0bb4`
- source-scoped BM25 uses bounded `retrieval_top_k=12`: L4DLHQUZ has 16 candidates with qrel rank 11; 3NLKTSIP has 18 candidates with qrel rank 12.
- Dry-run/preflight passed. No Key, HTTP, Provider, Tool, Writer, or Attempt-003 call was executed.
