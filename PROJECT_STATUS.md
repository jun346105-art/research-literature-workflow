# Project Status

Milestone: `v0.1-small-batch-e2e`

Status: v0.1 single-paper E2E completed; v0.1+ small-batch E2E acceptance completed.

## Completed Phases

- Phase 0: environment confirmation and project initialization planning.
- Phase 1A: paper-search-pro result reading, normalization, `candidate_pool.json`.
- Phase 1B: manual candidate selection and Zotero import export files.
- Phase 1C: paper-search-pro local skill workflow adapter and result inspection.
- Phase 2A: read-only Zotero collection snapshot.
- Phase 2B: Zotero snapshot to Obsidian inbox note templates.
- Phase 2C: Better BibTeX citation key diagnostics and Obsidian note checks.
- Phase 2D: citation-key note reconciliation planning and duplicate prevention.
- Phase 3A: local PDF text and Zotero annotation reading context.
- Phase 3B: reading context cleaning, section guessing, chunking, annotation alignment.
- Phase 3C: full context rebuild and quality gate.
- Phase 4A-mini: single-paper LLM structured reading note JSON.
- Phase 4B: structured note to reviewable Obsidian update preview.
- Phase 4C: approved preview applied to Obsidian marker region with backup.

## MVP Status

- v0.1 single-paper E2E completed.
- v0.1+ small-batch E2E acceptance completed.
- 8 papers imported/readied.
- 4 papers LLM structured reading passed.
- 4 previews generated.
- 2 notes applied with backup.
- pytest: 84 passed.

## Current E2E Loop

```text
paper-search-pro skill
-> candidate_pool.json
-> selected_candidates.json
-> selected.bib / selected.ris
-> Zotero
-> zotero_collection.json
-> Obsidian inbox note
-> reading_context
-> clean_reading_context
-> quality gate
-> LLM structured_reading_note
-> Obsidian update preview
-> approved apply into Obsidian marker region
```

## Freeze Notes

No v0.1+ feature work should add batch LLM reading, literature review generation, Zotero writes, PDF downloads, OCR, automatic Obsidian promotion, or automatic tag governance.
