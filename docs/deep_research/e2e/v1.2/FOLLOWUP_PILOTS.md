# Follow-up Pilot Designs after Attempt-008

These are design-only, unexecuted follow-ups. No Provider, Web, Tool or real E2E call is authorized by the closure batch.

Both designs bind to the cross-paper implementation commit `d286ca0c3a187d7237e399d766a2370f5683812b` (runtime source SHA-256 `76b894d0b596c16d804ba1fedd893a64e4e717a28de11a866e2ae673e65db2d3`), Planner prompt SHA-256 `cfd418a50d2c9a91230994a24bf0605f4db336fd557f0f2a13135112dee1bd3b`, Writer prompt SHA-256 `a0a3ead0fccac18ffb0d92e6e150b56e5943ad29971259b34b45431f176257e1`, and corpus SHA-256 `d099dc9ef22678af17ffbb12fc5198c9a6fce71d56576dde6f2b62984b8a7de6`. They use GLM-5.3-Flash, Planner low / Writer high reasoning, 2048/4096 Planner and 4096/4096 Writer token ceilings, two Provider calls, zero retries, one bounded replan, 60/180 second timeouts, 0.02 CNY hard limit, and no Web, vision, files, parallelism or fallback.

## Cross-paper comparison

The repository’s canonical task key is `cross_paper_comparison` (the user-facing design label is cross-paper compare).

- Attempt: `glm-5.3-flash-deepresearch-cross-paper-001`
- Executable plan: [glm_e2e_cross_paper_plan.attempt-001.json](glm_e2e_cross_paper_plan.attempt-001.json), schema `dr-glm-e2e-pilot-v1.2-cross-paper`
- Task/Brief: `dr-task-ee0fc936d6efdaf45c2d6566` / `dr-brief-0784ae0da15d3261fc5ca8f6`
- Deterministic run: `dr-run-8e3c2028b68e14c88fc7b17e`
- Artifact target: `outputs/deep_research/e2e/v1.2/dr-run-8e3c2028b68e14c88fc7b17e` (must be absent before any future execution)
- Frozen task input SHA-256: `4315f8de67e0cfd65c1e9ce4a296bb6fb6a08cf0652483627417df2a537bfe0e`.
- Selected corpus Sources: `dr-source-76a2766b4e0d53670687ff4e` (L4DLHQUZ / TPMN) and `dr-source-c82227e5b40e464045457dd3` (3NLKTSIP / Modified YOLO), with passages `L4DLHQUZ:L4DLHQUZ_chunk_0007` and `3NLKTSIP:3NLKTSIP_chunk_0005`.
- Gate: at least two independent Sources; every comparison Claim must retain source-specific Evidence and Citation/Quote/span grounding. A conflict or replan is not forced when the corpus does not support one.

## Insufficient evidence

- Attempt: `glm-5.3-flash-deepresearch-insufficient-evidence-001`
- Task/Brief: `dr-task-4e78911df9ce081d08aacf6a` / `dr-brief-84aad028176f94da6be6aef7`
- Deterministic run: `dr-run-def2aef07b645306d3be21d1`
- Artifact target: `outputs/deep_research/e2e/v1.2/dr-run-def2aef07b645306d3be21d1` (must be absent before any future execution)
- Gate: no unsupported Claim or fabricated Citation; a structured abstention reason is required; `insufficient_evidence` or safe `partial` is acceptable and is not a system failure.

The machine-readable design is [followup_pilot_designs.json](followup_pilot_designs.json). Each pilot requires separate manual authorization and a fresh artifact audit; neither is part of Attempt-008 closure.
