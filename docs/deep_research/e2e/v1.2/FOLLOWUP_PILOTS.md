# Follow-up Pilot Designs after Attempt-008

These are controlled follow-up designs. Attempt-001 and Attempt-002 were each executed once and remain immutable known failures. Cross-paper Attempt-003 was then executed once and closed as `real_cross_paper_comparison_e2e_pass_under_frozen_source_scoped_corpus`. The insufficient-evidence plan below is a new dry-run/preflight-only plan; no additional Provider, Web, Tool or real E2E call is authorized by the current batch.

The original design records preserve their pre-repair identity. Attempt-003 binds the stabilization implementation commit `0b78a9375133c4ce9350c528ea208416f66fbafd` (runtime source SHA-256 `45ec8551698385ee218eac2a9adf74fa624b41a0efa7d2b7e8cbfa45a7da3287`), cross Planner prompt SHA-256 `ed51df7a0c3223abbe20d1b0386c6bba5665437f7cb1490977e5f4e3704ca5f9`, Writer prompt SHA-256 `caa0cffb9495863b95ae1e6e9e0945797b5776c727830093d7568fe6cf957445`, and corpus SHA-256 `d099dc9ef22678af17ffbb12fc5198c9a6fce71d56576dde6f2b62984b8a7de6`. It keeps GLM-5.3-Flash, Planner low / Writer high reasoning, 2048/4096 Planner and 4096/4096 Writer ceilings, two Provider calls, zero retries, one bounded replan, 60/180 second timeouts, 0.02 CNY hard limit, source-scoped retrieval `top_k=12`, and no Web, vision, files, parallelism or fallback.

## Cross-paper comparison

The repository’s canonical task key is `cross_paper_comparison` (the user-facing design label is cross-paper compare).

- Attempt: `glm-5.3-flash-deepresearch-cross-paper-001`
- Executable plan: [glm_e2e_cross_paper_plan.attempt-001.json](glm_e2e_cross_paper_plan.attempt-001.json), schema `dr-glm-e2e-pilot-v1.2-cross-paper`
- Task/Brief: `dr-task-ee0fc936d6efdaf45c2d6566` / `dr-brief-0784ae0da15d3261fc5ca8f6`
- Deterministic run: `dr-run-8e3c2028b68e14c88fc7b17e`
- Artifact: `outputs/deep_research/e2e/v1.2/dr-run-8e3c2028b68e14c88fc7b17e` (retained `failed_known / cross_paper_comparison_invalid`; not modified)
- Frozen task input SHA-256: `4315f8de67e0cfd65c1e9ce4a296bb6fb6a08cf0652483627417df2a537bfe0e`.
- Selected corpus Sources: `dr-source-76a2766b4e0d53670687ff4e` (L4DLHQUZ / TPMN) and `dr-source-c82227e5b40e464045457dd3` (3NLKTSIP / Modified YOLO), with passages `L4DLHQUZ:L4DLHQUZ_chunk_0007` and `3NLKTSIP:3NLKTSIP_chunk_0005`.
- Gate: at least two independent Sources; every comparison Claim must retain source-specific Evidence and Citation/Quote/span grounding. A conflict or replan is not forced when the corpus does not support one.

Attempt-001 audit found two real Sources but no Claim whose citations covered both Sources, and the runtime graph used Q55RU9N6 instead of the plan-selected L4DLHQUZ. The original artifact and plan remain unchanged.

## Repaired cross-paper Attempt-002

- Executable plan: [glm_e2e_cross_paper_plan.attempt-002.json](glm_e2e_cross_paper_plan.attempt-002.json)
- Attempt: `glm-5.3-flash-deepresearch-cross-paper-002`
- Deterministic run: `dr-run-b966de61dabf031cbfa96d3e`
- Artifact: `outputs/deep_research/e2e/v1.2/dr-run-b966de61dabf031cbfa96d3e` (retained `failed_known / selected_source_evidence_missing`; not modified)
- Implementation commit/source SHA-256: `265470ce7ec7bdc70f41df29037e55c896b1c65a` / `b133c7ddd00ff9d53ced077ace11300e7f51e04649b35417061a011d4a9ff23a`
- Planner/Writer prompt SHA-256: `67f3c0b64867238b028ba210daa27affdbd11d2af945e2dd0967136e71cb4ae7` / `caa0cffb9495863b95ae1e6e9e0945797b5776c727830093d7568fe6cf957445`
- Selected Sources: `dr-source-76a2766b4e0d53670687ff4e` and `dr-source-c82227e5b40e464045457dd3`; selected passages are `L4DLHQUZ:L4DLHQUZ_chunk_0007` and `3NLKTSIP:3NLKTSIP_chunk_0005`.

Attempt-002 enforces source/passage allowlists before EvidenceGraph admission and requires a structurally cross-source Claim before Writer success. It was executed once, failed at source/evidence business validation after a successful search operation, and remains immutable.

## Cross-paper Attempt-003 closure

- Executable plan: [glm_e2e_cross_paper_plan.attempt-003.json](glm_e2e_cross_paper_plan.attempt-003.json)
- Attempt: `glm-5.3-flash-deepresearch-cross-paper-003`
- Deterministic run: `dr-run-02a0613ba863c12bf851a58e`
- Artifact: `outputs/deep_research/e2e/v1.2/dr-run-02a0613ba863c12bf851a58e` (retained; closure manifest: [cross_paper_result_manifest.attempt-003.json](cross_paper_result_manifest.attempt-003.json))
- Selected Sources/passages: L4DLHQUZ → `L4DLHQUZ:L4DLHQUZ_chunk_0007`; 3NLKTSIP → `3NLKTSIP:3NLKTSIP_chunk_0005`.
- Source-scoped BM25 is bounded at `top_k=12`; offline qrel ranks are 11/16 and 12/18 within the respective source candidates. The runtime preserves successful Tool operations and terminalizes known business validation failures with a final failed lifecycle/checkpoint.
- Result: `real_cross_paper_comparison_e2e_pass_under_frozen_source_scoped_corpus`. Semantic correctness remains unverified; `author_review_required=true` and `publication_ready=false`.

## Insufficient evidence

- Attempt: `glm-5.3-flash-deepresearch-insufficient-evidence-002`
- Executable plan: [glm_e2e_insufficient_evidence_plan.attempt-002.json](glm_e2e_insufficient_evidence_plan.attempt-002.json)
- Task/Brief: `dr-task-8868fb9d04f57c97a2c552f7` / `dr-brief-f2a931da15c97591a9de5482`
- Deterministic run: `dr-run-97bad8fbd966fcc8c1f049f3`
- Artifact target: `outputs/deep_research/e2e/v1.2/dr-run-97bad8fbd966fcc8c1f049f3` (absent)
- Corpus audit: the frozen 185-passage packaging/vision corpus contains no direct `mars`, `orbital`, `propellant` or `orbiter` terms for the selected mission-parameter question.
- Gate: no unsupported Claim or fabricated Citation; a structured abstention reason is required; `insufficient_evidence` or safe `partial` is acceptable and is not a system failure.

The original machine-readable design remains [followup_pilot_designs.json](followup_pilot_designs.json). Insufficient-evidence execution requires separate manual authorization and a fresh artifact audit; it was not executed in this batch.
