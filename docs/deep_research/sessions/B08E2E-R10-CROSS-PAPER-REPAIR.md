# B08E2E-R10 — Cross-paper Attempt-001 Repair and Attempt-002 Freeze

Status: `completed` / `design_only`; final state `ready_for_cross_paper_attempt002_manual_execute`. No Key was read, no HTTP was sent, and Attempt-002 was not executed.

Attempt-001 (`dr-run-8e3c2028b68e14c88fc7b17e`) remains permanently retained as `failed_known / cross_paper_comparison_invalid`. Its runtime SHA-256 is `FC34EE6F305173A2B29552D809B6DEB9FC8F44554D9621D555CE827273407DC9`, checkpoint SHA-256 is `7F6EBFA8CC949903C58728AB0CAA4EA413315BA1E8B8986E5CF7E72CB1626050`, and its plan/artifact were not modified.

The failure occurred after one successful Planner Provider call and four successful local Tool calls, at the deterministic cross-paper validation gate. The graph had two real Sources and two real EvidenceUnits, but `comparison_claim_count=0`; no Claim had Citation coverage across two Sources. The historical raw Writer draft was not persisted, so its exact shape is not asserted. The graph also used Q55RU9N6 instead of the plan-selected L4DLHQUZ, exposing the need for runtime source selection enforcement.

## Repair

The existing LocalResearchExecutor now accepts optional program-owned source/passage allowlists. Cross-paper CLI execution passes the immutable selected keys and passage IDs; unselected candidates or retrieval results are rejected before EvidenceGraph admission. A deterministic Writer gate requires at least one Claim whose Citation suggestions cover two distinct Source IDs, without merging unrelated single-source Claims or manufacturing a comparison. Cross-specific Planner and Writer prompts identify the selected sources and require comparison rather than separate summaries. Runtime reducer, checkpoint, replay, budget and retry semantics are unchanged.

## Attempt-002

The new immutable plan is [glm_e2e_cross_paper_plan.attempt-002.json](../e2e/v1.2/glm_e2e_cross_paper_plan.attempt-002.json):

- attempt: `glm-5.3-flash-deepresearch-cross-paper-002`
- run: `dr-run-b966de61dabf031cbfa96d3e`
- artifact target: `outputs/deep_research/e2e/v1.2/dr-run-b966de61dabf031cbfa96d3e` (absent)
- implementation commit: `f1401b1fdd3b872340c11449dc2cfca926a913bc`
- runtime source SHA-256: `c61a1b961d1c5554ff797448017f56cc426e466e13b2dea6391b57a45d33650a`
- Planner/Writer prompt SHA-256: `67f3c0b64867238b028ba210daa27affdbd11d2af945e2dd0967136e71cb4ae7` / `caa0cffb9495863b95ae1e6e9e0945797b5776c727830093d7568fe6cf957445`
- task input SHA-256: `4315f8de67e0cfd65c1e9ce4a296bb6fb6a08cf0652483627417df2a537bfe0e`
- selected source keys: `L4DLHQUZ`, `3NLKTSIP`

Offline cross-paper tests cover selected-source enforcement, missing-source fail-closed behavior, source-specific Evidence, two-source comparison Claim requirements, replay safety, and artifact uniqueness. Attempt-002 remains pending separate manual authorization.
