# Insufficient-evidence Pilot Attempt-002 Closure

Result: `real_insufficient_evidence_abstention_pass_on_obvious_out_of_domain_query`.

The immutable plan [glm_e2e_insufficient_evidence_plan.attempt-002.json](e2e/v1.2/glm_e2e_insufficient_evidence_plan.attempt-002.json) was executed once for the question: “What was the orbital inclination and propellant mass of the Mars Reconnaissance Orbiter mission?” The frozen local corpus contains 185 passages from ten packaging/vision papers and no direct evidence for that mission question.

The run ended with `terminal=insufficient_evidence` and CLI exit code `2`, which is the expected known business terminal for this task. It used one successful GLM Structured Planner call, two successful local Tool calls (`search_local_corpus` and `read_passage`), and one successful GLM Single Writer call. There were two Provider calls, two Tool calls, zero retries and zero replans. Usage was 2,518 input / 234 output / 2,752 total tokens; cost `1334.8` micros; client-observed elapsed `4.405896s`.

BM25 returned one irrelevant packaging-vision passage (`3NLKTSIP:3NLKTSIP_chunk_0008`, Source `dr-source-c82227e5b40e464045457dd3`). This is a retrieval false positive, not evidence of Mars orbital inclination or propellant mass. The EvidenceUnit hash, Source identity, passage locator, page and span all match the frozen corpus, but the Writer produced a structured abstention with zero Claims and zero Citations. Therefore no unsupported Claim or fabricated citation was displayed. The result does not show that the Retriever itself recognized the no-answer case; abstention occurred at the Writer/Validator layer and incurred unnecessary passage-read, Writer tokens, latency and cost.

The final report has `status=insufficient_evidence`, `author_review_required=true`, `publication_ready=false`, no validation issues and no displayable Claim. Full replay and checkpoint+tail replay are equal, with zero Provider/Planner/Writer/Tool calls during replay. Runtime sequence and hash chain are valid, and the final checkpoint head equals the stream head. Credential material, reasoning text and private absolute paths were not persisted.

This is an obvious out-of-domain easy negative only. It does not establish hard-negative abstention, same-domain semantic correctness, retrieval quality at scale, or a large abstention benchmark. Historical Attempt-008 and Cross-paper Attempt-001/002/003 artifacts remain unchanged.

The machine-readable evidence inventory is [insufficient_evidence_result_manifest.attempt-002.json](e2e/v1.2/insufficient_evidence_result_manifest.attempt-002.json).
