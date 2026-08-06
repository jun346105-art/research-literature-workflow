# Evaluation Run 002: Development Pilot

## Scope

Evaluation Run 002 is a development pilot over three papers. It is not a held-out benchmark, and it is not an independent blinded expert evaluation. Baseline and Proposed claims are not paired claim-by-claim, so their counts should not be interpreted as a paired statistical comparison.

The private source artifacts are excluded from this repository because they may contain local paths, copyrighted PDF text, and human review material. This public report was generated from a verified private canonical aggregate. Its aggregate summary SHA-256 is `abf5626e1afac5bff70691bc0e1693f9643d1d83377ede1264e519783b64d087`. SHA-256 identifies the run and artifact integrity; it does not by itself make the result publicly reproducible. External readers cannot fully reproduce the real result without the private frozen inputs.

## Method

Both paths used the same frozen paper inputs and research context.

- **Baseline** used `raw-baseline-multichunk-v2` with the content contract `raw-baseline-content-v1`. It generated claims and evidence fields from multiple chunks. Baseline evidence was not anchored, repaired, deleted, or rewritten by the program before scoring.
- **Proposed** used `chunk-constrained-evidence-v1` followed by `evidence-bank-note-v1`: the model proposed short quote hints one chunk at a time; the program anchored a continuous source substring; the final note selected only anchored candidates; and final evidence passed strict exact validation.

System-owned metadata, including Zotero key, citation key, and title, came from the frozen manifest. Model-generated content included summaries, claims, quote hints, and candidate selections. The program owned candidate identifiers, chunk/page provenance, and final `evidence_text`; it did not trust the model to reproduce final quotations.

The Baseline made 3 calls. The Proposed path made 62 calls: 59 candidate calls and 3 final-note calls. This is not an equal-call, equal-token, equal-cost, or equal-latency comparison. The comparison evaluates evidence traceability across two pipeline architectures. Proposed uses finer-grained calls as an engineering tradeoff for verifiable evidence.

## Reproducibility

| Item | Value |
| --- | --- |
| LLM run Git SHA | `55754efb67dfa157865a9ed47098c4f058d3b821` |
| Public aggregation Git SHA | `d4cb25676f799bdf13bff7952fab610b52bf0703` |
| Model | `deepseek-v4-flash` |
| Temperature | `0` |
| Thinking | disabled |
| Response format | JSON object |
| Calls | 65, with 0 retries and 0 runner errors |
| Provider-reported usage | 65 / 65 calls |
| Input / output tokens | 128009 / 19778 |
| Reference cost | 0.167565 CNY |

The cost is a reference estimate under a fixed price assumption of 1 CNY per million input tokens and 2 CNY per million output tokens. It is not a provider invoice. `chars_div_4` was used only as a context-guard estimate; it is not a model tokenizer or measured token count.

## Results

| Metric | Baseline | Proposed |
| --- | ---: | ---: |
| Final evidence links | 23 | 37 |
| Strict exact grounding | 1 / 23 | 37 / 37 |
| Fully supported | 17 / 23 (73.9%) | 32 / 37 (86.5%) |
| Supported + partially supported | 23 / 23 (100%) | 36 / 37 (97.3%) |
| Accept | 16 / 23 (69.6%) | 26 / 37 (70.3%) |
| Revise | 7 / 23 (30.4%) | 10 / 37 (27.0%) |
| Reject | 0 / 23 (0%) | 1 / 37 (2.7%) |

The run processed 3 papers and 59 chunks. The Proposed candidate stage produced 100 candidates: 57 anchored and 43 failed. Candidate-bearing chunk coverage was 35 / 59. Successful anchors used 13 exact matches and 44 normalized-whitespace matches. Failures were 40 anchor-not-found and 3 ambiguous anchors.

Latency used the aggregate's nearest-rank statistics: overall p50/p95 was 2662.303 / 14512.357 ms across 65 calls. Baseline p50/p95 was 14455.197 / 18973.838 ms; candidate p50/p95 was 2591.414 / 3501.804 ms; final-note p50/p95 was 22309.764 / 22777.794 ms.

## Interpretation

The main result is improved evidence traceability and strict exact grounding, not a claim of universal accuracy improvement. Moving from 1 / 23 to 37 / 37 strict grounding shows that the final Proposed evidence strings were traceable to their declared chunks under this pipeline.

Strict grounding does not prove that a claim is semantically correct, eliminate hallucination, or establish a general accuracy rate. Baseline evidence often failed strict grounding while human review still found its content at least partially supported. Conversely, Proposed evidence still included one unsupported item and multiple items needing revision. Human review remains required.

The two paths have broadly similar human acceptance rates. This pilot therefore does not demonstrate a large semantic-quality improvement; its clearest result is strict evidence traceability.

Candidate chunk coverage is not retrieval recall: a chunk without an anchored candidate is not automatically irrelevant or incorrect.

## Known Limitations

- The sample has only three papers and is a development pilot.
- Labels were completed by the project author with AI-assisted translation, not by independent blinded experts.
- Baseline and Proposed evidence counts differ, and claims are not paired.
- Candidate anchoring succeeded for 57 / 100 candidates.
- PDF extraction can contain NUL-like artifacts, broken words, repeated headers, and other text noise.
- Historical reviewer notes have irreversible encoding loss. Fixed review labels remain complete, but notes are excluded from metrics and are not published.
- No PDF excerpts, API information, local paths, or Zotero storage paths are published with this report.

## Next Phase

The next planned phase is **v0.2.1 PDF Cleaning, Chunking, and Candidate Anchoring Hardening**.

- Classify the 43 anchoring failures deterministically.
- Clean Unicode, NUL-like artifacts, broken words, line breaks, headers, footers, and repeated text.
- Compare fixed-character, token-aware, and sentence/section-aware chunking.
- Record chunk size, overlap, section, and page provenance.
- Tune on the development set while reserving new held-out samples.
- Run Evaluation Run 003 after the hardening work.

This phase does not start a vector database, RAG, Agent, or VLM implementation.
