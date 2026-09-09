# B08E2E-R9 — Cross-paper Comparison Pilot Plan

Status: `completed` / `design_only`; final state `ready_for_cross_paper_manual_execute`. No Key was read and no Provider/API/HTTP call was made.

## Corpus audit

The frozen `outputs/rag_bm25_v1/passages.jsonl` contains 10 papers and 185 passages. The selected comparison is supported by two independent papers with distinct stable Source IDs:

- `dr-source-76a2766b4e0d53670687ff4e` — L4DLHQUZ, TPMN: *Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection*; method passage `L4DLHQUZ:L4DLHQUZ_chunk_0007` describes multi-level feature fusion across backbone levels.
- `dr-source-c82227e5b40e464045457dd3` — 3NLKTSIP, *Modified YOLO for tape-sealing defects in outer packaging of cigarette carton*; method passage `3NLKTSIP:3NLKTSIP_chunk_0005` describes multi-scale convolutional structures and CCFM/IRMA feature fusion.

Each passage is present in the frozen corpus, belongs to its selected paper, and has a verifiable page/chunk locator. No same-paper duplication, fabricated Evidence, Web lookup or forced conflict is used.

## Immutable plan

[glm_e2e_cross_paper_plan.attempt-001.json](../e2e/v1.2/glm_e2e_cross_paper_plan.attempt-001.json) freezes:

- attempt: `glm-5.3-flash-deepresearch-cross-paper-001`
- task/brief: `dr-task-ee0fc936d6efdaf45c2d6566` / `dr-brief-0784ae0da15d3261fc5ca8f6`
- run: `dr-run-8e3c2028b68e14c88fc7b17e`
- artifact target: `outputs/deep_research/e2e/v1.2/dr-run-8e3c2028b68e14c88fc7b17e` (absent)
- implementation commit: `d286ca0c3a187d7237e399d766a2370f5683812b`
- runtime source SHA-256: `76b894d0b596c16d804ba1fedd893a64e4e717a28de11a866e2ae673e65db2d3`
- task input SHA-256: `4315f8de67e0cfd65c1e9ce4a296bb6fb6a08cf0652483627417df2a537bfe0e`
- Planner/Writer Prompt SHA-256: `cfd418a50d2c9a91230994a24bf0605f4db336fd557f0f2a13135112dee1bd3b` / `a0a3ead0fccac18ffb0d92e6e150b56e5943ad29971259b34b45431f176257e1`
- corpus SHA-256: `d099dc9ef22678af17ffbb12fc5198c9a6fce71d56576dde6f2b62984b8a7de6`

The cross-paper gate requires at least two Sources, source-specific Evidence/Citation/Quote/span grounding, and at least one Claim whose citations cover both Sources. It does not force a conflict or replan. `author_review_required=true` and `publication_ready=false` remain mandatory.

Budget is reused from Attempt-008: Planner 2048/4096 tokens with low reasoning, Writer 4096/4096 with high reasoning, two Provider calls maximum, zero retries, one bounded replan, 60-second operation timeout, 180-second run timeout and 0.02 CNY hard limit. Web, vision, files, parallelism and fallback are disabled.

Dry-run/preflight passed. A real cross-paper Pilot requires separate manual authorization and a fresh artifact audit.
