# Project Status

## Current Milestone

- Last pushed/tagged release: `v0.1.1-anchored-evidence-pipeline`
- Current state: local-first evidence-grounded workflow with frozen QA and M2A translation-retrieval contracts; FastAPI service readiness is not reached.
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

For detailed acceptance metrics, see:

- [Evaluation and acceptance metrics](docs/EVALUATION.md)
- [评估与验收指标](docs/EVALUATION.zh-CN.md)
- [DOGFOOD_RUN_001](docs/DOGFOOD_RUN_001.md)

## Current Technical Level

The project is a working local-first MVP, not a hosted SaaS product. It demonstrates:

- backend-style file pipeline orchestration;
- CLI workflow boundaries;
- minimal FastAPI wrapper and Swagger UI demo;
- data model validation with Pydantic;
- OpenAI-compatible JSON-mode LLM calls;
- retry/error artifact handling;
- local PDF extraction and chunking;
- clean-context quality gate;
- strict evidence validation;
- programmatic evidence anchoring;
- evidence-bank grounded structured notes;
- Obsidian preview/apply safety boundaries;
- pytest coverage for the core trust boundaries.

## Known Limitations

- No Web UI yet.
- No Docker packaging.
- No OCR for scanned PDFs.
- No automatic PDF download.
- No automatic literature review generation.
- No automatic tag governance.
- No Zotero writes.
- No public hosted deployment.
- No production job queue or database-backed task state.
- No validated deep-reading object ingestion or methods-preview workflow yet.
- The human-reviewed qrels freeze is a 20-query pilot, not a large benchmark. Its metrics must not be presented as broad production guarantees.
- Historical Chinese retrieval artifacts generated from corrupted `query_zh` values are invalid and must not be cited; only a future author-confirmed UTF-8 qrels rerun can replace them.
- The human-reviewed pilot qrels freeze is limited to 20 queries. The current dense baseline right-truncates most 3500/400 passages at 512 tokens, so it is not a final retriever selection.
- Minimal fixed windowing (512 tokens, 64 overlap, max parent score) did not exceed BM25-ZH-raw on the human-reviewed pilot's Recall@10. BM25-ZH-raw is the MVP retriever; no further retrieval tuning is planned in this milestone.
- M2A is a 20-query pilot and has not yet smoke-tested a mixed-language corpus. Translation is retrieval-only and never replaces evidence text or user source queries.
- M2B uses one Chinese source that is retrieval-smoke eligible but remains `needs_manual_check` for LLM use because Chinese section headings are unknown to the existing section detector. The smoke does not establish broad mixed-language retrieval quality.

## Recommended Next Steps

1. M3: define and implement Evidence Matrix using frozen QA and retrieval artifacts.
2. Preserve frozen QA and translation contracts; do not reopen Prompt, Schema, Dense, Hybrid, Reranker, or bilingual retrieval tuning.
3. Keep FastAPI/UI work deferred until the evidence and writing chain reaches the MVP definition of done.
