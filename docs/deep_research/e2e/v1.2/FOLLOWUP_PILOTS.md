# Follow-up Pilot Designs after Attempt-008

These are controlled follow-up designs. Attempt-001 was executed once and is permanently retained as `failed_known / cross_paper_comparison_invalid`; the repaired Attempt-002 below is dry-run/preflight-only. No additional Provider, Web, Tool or real E2E call is authorized by the repair batch.

The original design records preserve their pre-repair identity. The repaired cross-paper Attempt-002 plan binds implementation commit `265470ce7ec7bdc70f41df29037e55c896b1c65a` (runtime source SHA-256 `b133c7ddd00ff9d53ced077ace11300e7f51e04649b35417061a011d4a9ff23a`), cross Planner prompt SHA-256 `67f3c0b64867238b028ba210daa27affdbd11d2af945e2dd0967136e71cb4ae7`, Writer prompt SHA-256 `caa0cffb9495863b95ae1e6e9e0945797b5776c727830093d7568fe6cf957445`, and corpus SHA-256 `d099dc9ef22678af17ffbb12fc5198c9a6fce71d56576dde6f2b62984b8a7de6`. It keeps GLM-5.3-Flash, Planner low / Writer high reasoning, 2048/4096 Planner and 4096/4096 Writer ceilings, two Provider calls, zero retries, one bounded replan, 60/180 second timeouts, 0.02 CNY hard limit, and no Web, vision, files, parallelism or fallback.

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

Attempt-001 audit found two real Sources but no Claim whose citations covered both Sources, and the runtime graph used Q55RU9N6 instead of the plan-selected L4DLHQUZ. The original artifact and plan remain unchanged.

## Repaired cross-paper Attempt-002

- Executable plan: [glm_e2e_cross_paper_plan.attempt-002.json](glm_e2e_cross_paper_plan.attempt-002.json)
- Attempt: `glm-5.3-flash-deepresearch-cross-paper-002`
- Deterministic run: `dr-run-b966de61dabf031cbfa96d3e`
- Artifact target: `outputs/deep_research/e2e/v1.2/dr-run-b966de61dabf031cbfa96d3e` (absent)
- Implementation commit/source SHA-256: `265470ce7ec7bdc70f41df29037e55c896b1c65a` / `b133c7ddd00ff9d53ced077ace11300e7f51e04649b35417061a011d4a9ff23a`
- Planner/Writer prompt SHA-256: `67f3c0b64867238b028ba210daa27affdbd11d2af945e2dd0967136e71cb4ae7` / `caa0cffb9495863b95ae1e6e9e0945797b5776c727830093d7568fe6cf957445`
- Selected Sources: `dr-source-76a2766b4e0d53670687ff4e` and `dr-source-c82227e5b40e464045457dd3`; selected passages are `L4DLHQUZ:L4DLHQUZ_chunk_0007` and `3NLKTSIP:3NLKTSIP_chunk_0005`.

Attempt-002 enforces source/passage allowlists before EvidenceGraph admission and requires a structurally cross-source Claim before Writer success. It remains unexecuted and requires separate manual authorization.

## Insufficient evidence

- Attempt: `glm-5.3-flash-deepresearch-insufficient-evidence-001`
- Task/Brief: `dr-task-4e78911df9ce081d08aacf6a` / `dr-brief-84aad028176f94da6be6aef7`
- Deterministic run: `dr-run-def2aef07b645306d3be21d1`
- Artifact target: `outputs/deep_research/e2e/v1.2/dr-run-def2aef07b645306d3be21d1` (must be absent before any future execution)
- Gate: no unsupported Claim or fabricated Citation; a structured abstention reason is required; `insufficient_evidence` or safe `partial` is acceptable and is not a system failure.

The machine-readable design is [followup_pilot_designs.json](followup_pilot_designs.json). Each pilot requires separate manual authorization and a fresh artifact audit; neither is part of Attempt-008 closure.
