# Project Status

## Current Milestone

- Last pushed/tagged release: `v1.0.0-mvp`
- Current state: `MVP_COMPLETE`. LitFlow is a local-first evidence-grounded bilingual research writing Copilot with frozen retrieval/QA contracts, Evidence Matrix, author-editable writing drafts, a localhost-only FastAPI/UI workbench, and verified Docker packaging.
- Latest additions after `v0.1.1`: reproducible evaluation, strict QA contracts, entity binding, safe partial answers, and author-reviewed Chinese-to-English retrieval translation.

## Completed

- Phase 0: environment confirmation and project initialization planning.
- Phase 1A/1B/1C: paper-search-pro result ingestion, candidate pool, manual selection, local skill workflow.
- Phase 2A/2B/2C/2D: read-only Zotero snapshot, Obsidian inbox note templates, citation-key diagnostics, duplicate prevention.
- Phase 3A/3B/3C: PDF reading context, clean context, chunking, annotation alignment, quality gate.
- Phase 4A-mini/4B/4C: single-paper structured reading, preview, approved Obsidian marker-region apply.
- v0.1+ small-batch E2E: 8 papers processed through Zotero, Obsidian notes, reading context, clean context, and quality gate.
- Phase 5A-5O: evidence audit, strict validation diagnosis, programmatic anchoring, chunk-constrained evidence extraction, evidence-bank grounded notes, anchored previews, and one anchored apply replacement pilot.
- Open-source presentation: sanitized examples, English/Chinese README, API demo, and architecture diagrams.
- Minimal FastAPI wrapper: safe HTTP endpoints for health check, evidence candidate bank generation, evidence-bank note generation, and Obsidian preview generation.
- v0.3A deep-reading object ingestion: experimental and currently unvalidated. Two development responses were preserved, but neither satisfied the strict canonical object schema; it is not a production feature.
- Human-reviewed pilot qrels: a 20-query freeze with `BM25-ZH-raw` and `top_k=10` selected as the bounded MVP retriever. Fixed Dense Windowing and Hybrid did not exceed BM25-ZH-raw on Recall@10.
- QA v1.2 Final Unified Flash Pilot: 20 one-shot calls, 17 execution-success outcomes, 9 grounded displayed answers, 8 valid abstentions, and 3 visible execution failures. Displayed citation validity, strict quote grounding, and claim-citation coverage were all 100%.
- Author review of the unified Flash pilot: 9/9 displayed answers were usable after review (6 pass, 3 minor revision); no-answer abstention was 3/3 correct. Answerable-query grounded-answer success was 9/17 (52.9%), so execution availability and answerable coverage remain limited.
- M2A Translation Retrieval: 20/20 machine translations were author-reviewed as usable. On the same human-reviewed pilot, BM25-EN-machine-translated improved Recall@10 from 0.6275 to 0.7157 (+0.0882) and recovered Q10/Q11 Top-10 misses. Human English queries remain oracle-style reference only.
- M2B Mixed-Language Corpus Smoke: one real Chinese engineering PDF added six page-provenanced mixed-language passages to an isolated 191-passage smoke corpus. All six routes completed, but the Chinese-to-Chinese query did not retrieve the expected paper; status is `pass_with_known_limit` and bilingual retrieval development is closed.
- M3 Evidence Matrix: 16 author-reviewed QA claims across four papers were converted into citation/quote-revalidated EvidenceRecords with claim ledger, paper comparison, and review packet views. Two partial records preserve the TPMN coverage gap; 30 sparse matrix cells are explicitly marked as lacking reviewed evidence.
- M4 Writing Vertical Slice: six bilingual comparison sentences were generated from reviewed EvidenceRecords, then author-reviewed and corrected in an independent closure artifact. Final sentence-to-record coverage is 100%; the outcome is `pass_with_moderate_human_revision` and `validated_as_author_editable_draft`, not publication-ready prose.
- M5 Minimal FastAPI + Simple UI MVP: versioned read-only corpus, retrieval, passage, Evidence Matrix, and writing-draft endpoints plus file-backed job status and SSE events are available on localhost. Offline demo mode and an online Q01 Flash UI job are verified, including cached Chinese-to-English retrieval, entity binding, citation membership, strict quote grounding, and citation drawer rendering. Q05 remains a historical safe failure because its ambiguous quote also matched another passage; no validator was relaxed and no retry was attempted.
- M6 Runtime Container Smoke Closure: verified a non-root, read-only-root-filesystem Docker image with localhost-only default port, read-only demo inputs, persisted job recovery, explicit Online QA fail-closed behavior, and named online job-volume restart persistence. No cloud deployment or image publication was performed.
- M8 Experimental Agent Extension Closure: M8A controlled single-agent scaffold, M8B.1A durable event/replay kernel, and M8B.1B progress-aware control-plane Fake E2E passed. The real AG01 Flash planning/tool chain completed, but the final grounded answer failed strict quote grounding (`evidence_anchor_not_found`); AG07/AG11 real canaries and the 12-task pilot were not run due to the frozen gate. Overall status: `experimental_partial_pass`, not a validated end-to-end grounded Agent product.

For detailed acceptance metrics, see:

- [Evaluation and acceptance metrics](docs/EVALUATION.md)
- [评估与验收指标](docs/EVALUATION.zh-CN.md)
- [DOGFOOD_RUN_001](docs/DOGFOOD_RUN_001.md)

## Current Technical Level

The project is a working local-first MVP, not a hosted SaaS product. It demonstrates:

- backend-style file pipeline orchestration;
- CLI workflow boundaries;
- minimal FastAPI wrapper and Swagger UI demo;
- localhost-only static browser MVP with evidence and writing artifact views;
- data model validation with Pydantic;
- OpenAI-compatible JSON-mode LLM calls;
- retry/error artifact handling;
- local PDF extraction and chunking;
- clean-context quality gate;
- strict evidence validation;
- programmatic evidence anchoring;
- evidence-bank grounded structured notes;
- author-reviewed evidence-grounded bilingual draft rendering;
- Obsidian preview/apply safety boundaries;
- pytest coverage for the core trust boundaries.

## Known Limitations

- No OCR for scanned PDFs.
- No automatic PDF download.
- No automatic literature review generation.
- No automatic tag governance.
- No Zotero writes.
- No public hosted deployment.
- No production job queue or database-backed task state.
- No validated deep-reading object ingestion or methods-preview workflow yet.
- The M4 writing output is an author-editable draft, not a publication-ready manuscript or a complete literature review.
- M5 has one validated online vertical slice, not a broad availability guarantee. Q05 remains a safe cross-passage ambiguity rejection, and the frozen QA pilot's answerable-query coverage limitations still apply.
- The human-reviewed qrels freeze is a 20-query pilot, not a large benchmark. Its metrics must not be presented as broad production guarantees.
- Historical Chinese retrieval artifacts generated from corrupted `query_zh` values are invalid and must not be cited; only a future author-confirmed UTF-8 qrels rerun can replace them.
- The human-reviewed pilot qrels freeze is limited to 20 queries. The current dense baseline right-truncates most 3500/400 passages at 512 tokens, so it is not a final retriever selection.
- Minimal fixed windowing (512 tokens, 64 overlap, max parent score) did not exceed BM25-ZH-raw on the human-reviewed pilot's Recall@10. BM25-ZH-raw is the MVP retriever; no further retrieval tuning is planned in this milestone.
- M2A translation is retrieval-only and never replaces evidence text or user source queries.
- M2B uses one Chinese source that is retrieval-smoke eligible but remains `needs_manual_check` for LLM use because Chinese section headings are unknown to the existing section detector. The smoke does not establish broad mixed-language retrieval quality.
- Evidence Matrix is a vertical slice from the current reviewed QA pilot, not a complete literature review. Sparse cells must not be filled with model knowledge.
- M8 Agent is an experimental extension. Its planning/tool-control chain and durable replay kernel are verified, but end-to-end grounded Agent completion is not validated because AG01 stopped at strict quote grounding. Do not present an Agent completion rate, production Agent availability, a passed 12-task benchmark, MCP completion, or multi-Agent capability.

## Recommended Next Steps

1. MVP technical development is frozen at `v1.0.0-mvp`.
2. Preserve retrieval, QA, evidence, writing, UI, and Docker contracts unless a separately approved post-MVP milestone is defined.
3. Keep publication-oriented writing, cloud deployment, and feature expansion out of the MVP release scope.
