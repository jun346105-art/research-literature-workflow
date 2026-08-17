# Project Status

## Current Milestone

- Last pushed/tagged release: `v0.1.1-anchored-evidence-pipeline`
- Current state: `v0.1.1+` showcase-ready local-first MVP
- Latest additions after `v0.1.1`: minimal FastAPI wrapper, API demo, bilingual README, and README architecture diagrams.

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
- Passage-level BM25: an offline baseline built on AI-drafted silver qrels. Its retrieval metrics are preliminary and require human qrels review before external claims.

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
- BM25 qrels are AI-drafted silver labels, not human-validated benchmarks.

## Recommended Next Steps

1. Add GitHub Actions CI for `python -m pytest -q`.
2. Add a short demo script for interviews and GitHub visitors.
3. Keep the FastAPI wrapper minimal until the CLI pipeline stabilizes further.
4. Consider a thin UI only after the API demo and CI are clean.
