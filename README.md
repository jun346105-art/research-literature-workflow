# Research Literature Workflow

A local-first research literature workflow connecting `paper-search-pro`, Zotero, Obsidian, and OpenAI-compatible LLMs for structured, evidence-grounded paper reading.

一个本地优先的科研文献工作流工具，用于连接 paper-search-pro、Zotero、Obsidian 与兼容 OpenAI API 的大模型，实现可审计、可人工确认的结构化文献精读。

## v0.1 MVP

The current milestone is `v0.1-single-paper-e2e`: one complete single-paper loop from literature discovery results to an approved Obsidian marker-region update.

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
-> LLM structured_reading_note
-> Obsidian update preview
-> approved apply into Obsidian marker region
```

## Tool Boundaries

- `paper-search-pro`: discovery layer only.
- Zotero: authoritative metadata, PDF, annotation, and citation key source.
- Obsidian: local Markdown knowledge base.
- LLM: optional single-paper structured reading assistant.
- `litflow`: local automation glue; it does not replace Zotero or Obsidian.

## Quick Workflow

```powershell
$env:PYTHONPATH = "src"

python -m litflow.cli inspect-psp-results --input "<paper-search-pro-result-dir>"

python -m litflow.cli build-candidate-pool `
  --input "<paper-search-pro-result-dir>" `
  --output ".\outputs\candidate_pool.json"

python -m litflow.cli select-candidates `
  --candidates ".\outputs\candidate_pool.json" `
  --out ".\outputs\selected_candidates.json"

python -m litflow.cli export-zotero-import `
  --selected ".\outputs\selected_candidates.json" `
  --format bib `
  --out ".\outputs\selected.bib"

python -m litflow.cli read-zotero-collection `
  --collection "Collection Name" `
  --output ".\outputs\zotero_collection.json"

python -m litflow.cli make-obsidian-notes `
  --items ".\outputs\zotero_collection.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview"

python -m litflow.cli build-reading-context `
  --items ".\outputs\zotero_collection.json" `
  --out-dir ".\outputs\reading_context" `
  --manifest ".\outputs\reading_context_manifest.json"

python -m litflow.cli clean-reading-context `
  --context-dir ".\outputs\reading_context" `
  --manifest ".\outputs\reading_context_manifest.json" `
  --out-dir ".\outputs\clean_reading_context" `
  --out-manifest ".\outputs\clean_reading_context_manifest.json"

python -m litflow.cli audit-clean-context `
  --clean-dir ".\outputs\clean_reading_context" `
  --manifest ".\outputs\clean_reading_context_manifest.json" `
  --out ".\outputs\clean_context_quality_report.json"

python -m litflow.cli read-paper-with-llm `
  --clean-context ".\outputs\clean_reading_context\PAPER.json" `
  --out ".\outputs\structured_reading_notes\PAPER.json"

python -m litflow.cli preview-obsidian-update `
  --structured-note ".\outputs\structured_reading_notes\PAPER.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview" `
  --out ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --manifest ".\outputs\obsidian_update_preview_manifest.json"

python -m litflow.cli apply-obsidian-update `
  --preview ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --target "<ObsidianVault>\00_Inbox\LiteratureReview\@zotero_KEY.md" `
  --manifest ".\outputs\obsidian_update_apply_manifest.json" `
  --approved
```

Full command notes: [docs/END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md)

Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

Status: [PROJECT_STATUS.md](PROJECT_STATUS.md)

paper-search-pro local skill workflow: [docs/PAPER_SEARCH_PRO_SKILL_WORKFLOW.md](docs/PAPER_SEARCH_PRO_SKILL_WORKFLOW.md)

## Environment

Copy `.env.example` and fill only local values. Do not commit real keys.

```text
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
ZOTERO_LIBRARY_ID=
ZOTERO_API_KEY=
OBSIDIAN_VAULT_PATH=
PAPER_SEARCH_PRO_RESULT_DIR=
```

## Safety Model

- Zotero is read-only in automated steps.
- Obsidian updates require preview review and explicit `--approved`.
- Applying an Obsidian update creates a backup first.
- LLM evidence links are validated against chunk IDs, page ranges, and source text.
- LLM output is not trusted as final knowledge without human review.

## v0.1 Limitations

- Only the single-paper LLM reading loop has been validated.
- No automatic PDF download.
- No OCR for scanned PDFs.
- No direct literature review generation.
- No automatic write into formal Obsidian library folders.
- No guarantee that section detection is perfect.
- LLM output must pass evidence validation and human confirmation.

## Development Check

```powershell
$env:PYTHONPATH='src;C:\Users\GigaByte\Documents\Codex\2026-07-01\obsidian\work\pydeps'
python -m pytest -q -p no:cacheprovider --basetemp ".\pytest_tmp_v01"
```
