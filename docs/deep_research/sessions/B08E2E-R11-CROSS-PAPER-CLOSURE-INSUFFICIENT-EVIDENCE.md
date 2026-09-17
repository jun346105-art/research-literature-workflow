# B08E2E-R11 — Cross-paper Closure and Insufficient-evidence Plan

Status: `completed` / `design_only`; final state `ready_for_insufficient_evidence_manual_execute`. No Key was read and no Provider/API/HTTP call was made in this batch.

## Cross-paper Attempt-003 closure

The independently audited result is `real_cross_paper_comparison_e2e_pass_under_frozen_source_scoped_corpus`. The immutable artifact is `outputs/deep_research/e2e/v1.2/dr-run-02a0613ba863c12bf851a58e` and its complete file hashes are recorded in [the result manifest](../e2e/v1.2/cross_paper_result_manifest.attempt-003.json). The runtime contains 26 ordered events with a valid hash chain and a final checkpoint head equal to the stream head.

The run completed one GLM Planner call, four successful local Tool calls (two searches and two passage reads), and one GLM Writer call. The graph contains exactly the two frozen Sources and their two selected passages. It contains six Claims and eight Citations, including one Claim whose Citations cover both Source IDs. Deterministic quote/span/locator grounding passed. Token usage was 4,561 input / 1,562 output / 6,123 total; cost `4011.2` micros; client-observed elapsed `12.4413195s`; retries and replans were zero. Full replay and checkpoint replay matched with zero external calls.

This result is limited to the frozen source-scoped corpus and `retrieval_top_k=12` (qrel ranks 11 and 12). It does not establish open-domain recall, semantic correctness, publication readiness, Web, multimodal or Multi-Agent capability. `author_review_required=true`, `publication_ready=false`, and `semantic_correctness_verified=false` remain in force.

## Insufficient-evidence Pilot freeze

The new plan is [glm_e2e_insufficient_evidence_plan.attempt-002.json](../e2e/v1.2/glm_e2e_insufficient_evidence_plan.attempt-002.json):

- attempt: `glm-5.3-flash-deepresearch-insufficient-evidence-002`
- run: `dr-run-97bad8fbd966fcc8c1f049f3`
- artifact target: `outputs/deep_research/e2e/v1.2/dr-run-97bad8fbd966fcc8c1f049f3` (absent)
- implementation commit: `72388ea5570ac5955c3e8dcf02e74f774835ecb5`
- runtime source SHA-256: `dc5b5d631ff1379decf98fed19007606c06d0343f3e152f8731191813f4fc767`
- Planner/Writer prompt SHA-256: `cfd418a50d2c9a91230994a24bf0605f4db336fd557f0f2a13135112dee1bd3b` / `a0a3ead0fccac18ffb0d92e6e150b56e5943ad29971259b34b45431f176257e1`
- corpus SHA-256: `d099dc9ef22678af17ffbb12fc5198c9a6fce71d56576dde6f2b62984b8a7de6`
- task input SHA-256: `b24487b3a080198b19fab35864c92b81024adc4b353b0add6b70f31ef2c742de`
- policy: Planner 1, Writer 1, retries 0, max replans 1, 60/180 second timeouts, 0.02 CNY, no Web/vision/files/parallel/fallback/Multi-Agent.

The question asks for Mars Reconnaissance Orbiter orbital inclination and propellant mass. The frozen 185-passage corpus contains ten packaging/vision papers and no direct `mars`, `orbital`, `propellant` or `orbiter` terms. This is a corpus-bounded abstention probe, not an artificially emptied corpus. A successful run must return `insufficient_evidence`, or a grounded `partial` with no unsupported Claim; fabricated Evidence, Citation, Quote or span is forbidden. `publication_ready` remains false and replay must produce zero external calls.

Only offline model/schema tests and CLI dry-run/preflight were run. Real insufficient-evidence execution remains separately gated and was not performed.
