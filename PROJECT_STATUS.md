# Project Status

## Current Milestone

- Last pushed/tagged release: `v0.1-small-batch-e2e`
- Current local state: Phase 5 anchored evidence pipeline completed
- Suggested next tag after review: `v0.1.1-anchored-evidence-pipeline`

## Completed

- Phase 0: environment confirmation and project initialization planning.
- Phase 1A/1B/1C: paper-search-pro result ingestion, candidate pool, manual selection, local skill workflow.
- Phase 2A/2B/2C/2D: read-only Zotero snapshot, Obsidian inbox note templates, citation-key diagnostics, duplicate prevention.
- Phase 3A/3B/3C: PDF reading context, clean context, chunking, annotation alignment, quality gate.
- Phase 4A-mini/4B/4C: single-paper structured reading, preview, approved Obsidian marker-region apply.
- v0.1+ small-batch E2E: 8 papers processed through Zotero, Obsidian notes, reading context, clean context, and quality gate.
- Phase 5A-5O: evidence audit, strict validation diagnosis, programmatic anchoring, chunk-constrained evidence extraction, evidence-bank grounded notes, anchored previews, and one anchored apply replacement pilot.

## Validated Results

- paper-search-pro candidates: 50
- selected papers: 8
- Zotero collection snapshot: 8 papers
- `pdf_exists=true`: 8 papers
- Obsidian inbox notes: 8
- reading_context: 8
- clean_reading_context: 8
- quality gate `ready_for_llm`: 8
- original LLM structured reading: 4
- anchored evidence candidate banks: 4
- anchored final structured notes: 4
- anchored previews ready: 4
- anchored apply replacement: 1 paper
- latest pytest result: 97 passed

## Current Technical Level

The project is a working local-first MVP, not a hosted product. It demonstrates:

- backend-style file pipeline orchestration;
- data model validation with Pydantic;
- OpenAI-compatible JSON-mode LLM calls;
- retry/error artifact handling;
- local PDF extraction and chunking;
- strict evidence validation;
- evidence anchoring;
- Obsidian preview/apply safety boundaries;
- pytest coverage for the core trust boundaries.

## Known Limitations

- No FastAPI wrapper yet.
- No Web UI.
- No Docker packaging.
- No OCR for scanned PDFs.
- No automatic PDF download.
- No automatic literature review generation.
- No automatic tag governance.
- No Zotero writes.
- No production job queue or database-backed task state.

## Recommended Next Steps

1. Finish open-source cleanup and sanitized examples.
2. Commit Phase 5 anchored evidence pipeline.
3. Tag `v0.1.1-anchored-evidence-pipeline`.
4. Add a minimal FastAPI wrapper only after the CLI project is clean and documented.
