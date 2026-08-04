# Research Literature Workflow

A local-first research literature workflow connecting `paper-search-pro`, Zotero, Obsidian, and OpenAI-compatible LLMs for structured, evidence-grounded paper reading.

中文定位：一个本地优先的科研文献工作流工具，用于连接 paper-search-pro、Zotero、Obsidian 与兼容 OpenAI API 的大模型，实现可审计、可人工确认、证据可回溯的结构化文献精读。

## What It Does

`litflow` is not a generic AI paper summarizer. It is a local workflow layer:

```text
paper-search-pro results
-> candidate_pool.json
-> manual selection
-> BibTeX / RIS export
-> user imports into Zotero
-> read-only Zotero snapshot
-> Obsidian inbox notes
-> PDF reading context
-> clean chunks + quality gate
-> evidence candidate bank
-> structured reading note
-> Obsidian preview
-> approved marker-region apply
```

The important design choice: LLM text is not trusted directly. Evidence snippets are anchored back to source chunks and validated before they can enter an Obsidian note.

## Core Capabilities

- Read `paper-search-pro` output files without modifying upstream skill code.
- Generate candidate pools and manual selection templates.
- Export selected papers to BibTeX / RIS for manual Zotero import.
- Read Zotero collections without writing Zotero or touching Zotero SQLite.
- Create Obsidian inbox note templates from Zotero snapshots.
- Extract local text PDFs with page-level metadata.
- Clean text, guess sections, chunk documents, and run quality gates.
- Build chunk-constrained evidence candidate banks.
- Generate structured reading notes from anchored evidence banks.
- Generate reviewable Obsidian update previews.
- Apply approved previews into a marker region with backup.

## Safety Boundaries

- Zotero automation is read-only.
- PDF handling is local-only; no automatic PDF download.
- Obsidian writes require preview review and explicit `--approved`.
- Apply updates only replace:

```markdown
<!-- LITFLOW_STRUCTURED_READING_START -->
...
<!-- LITFLOW_STRUCTURED_READING_END -->
```

- YAML frontmatter and marker-external user content are preserved.
- `.env`, PDF files, Zotero databases, private Obsidian vaults, and generated `outputs/` are ignored by git.

## Anchored Evidence Pipeline

The current strongest path is the anchored pipeline:

```powershell
$env:PYTHONPATH = "src"

python -m litflow.cli build-evidence-candidate-bank `
  --clean-context ".\outputs\clean_reading_context\PAPER.json" `
  --out ".\outputs\evidence_candidate_banks\PAPER_evidence_candidates.json" `
  --report ".\outputs\evidence_candidate_banks\PAPER_evidence_candidates_report.json"

python -m litflow.cli generate-note-from-evidence-bank `
  --candidate-bank ".\outputs\evidence_candidate_banks\PAPER_evidence_candidates.json" `
  --clean-context ".\outputs\clean_reading_context\PAPER.json" `
  --out ".\outputs\structured_reading_notes\PAPER_anchored_final.json" `
  --zotero-key "PAPER" `
  --citation-key "paper2026sample" `
  --title "Sample Paper Title"

python -m litflow.cli preview-obsidian-update `
  --structured-note ".\outputs\structured_reading_notes\PAPER_anchored_final.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview" `
  --out ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --manifest ".\outputs\obsidian_update_preview_manifest.json"
```

Only after manual review:

```powershell
python -m litflow.cli apply-obsidian-update `
  --preview ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --target "<ObsidianVault>\00_Inbox\LiteratureReview\@paper2026sample.md" `
  --manifest ".\outputs\obsidian_update_apply_manifest.json" `
  --approved
```

## End-to-End Workflow

Full command chain: [docs/END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md)

Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

Status: [PROJECT_STATUS.md](PROJECT_STATUS.md)

paper-search-pro local skill workflow: [docs/PAPER_SEARCH_PRO_SKILL_WORKFLOW.md](docs/PAPER_SEARCH_PRO_SKILL_WORKFLOW.md)

Open-source sample data: [examples/README.md](examples/README.md)

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

## Current Status

- `v0.1-small-batch-e2e`: completed and tagged.
- Phase 5 anchored evidence pipeline: implemented locally after v0.1.
- 8-paper small-batch workflow validated.
- 4-paper LLM reading workflow validated.
- Anchored evidence pipeline generated candidate banks, grounded notes, and previews for remaining batch papers.
- Current test count: 97 passed.

## Limitations

- This is a local CLI workflow, not a hosted SaaS product.
- No OCR for scanned PDFs.
- No automatic literature review generation.
- No automatic tag governance.
- No direct Zotero writes.
- No automatic Obsidian promotion into formal folders.
- Section detection is a lightweight heuristic.
- LLM output still requires schema validation, evidence validation, and human review.

## Development Check

```powershell
$env:PYTHONPATH='src;C:\Users\GigaByte\Documents\Codex\2026-07-01\obsidian\work\pydeps'
python -m pytest -q -p no:cacheprovider --basetemp ".\pytest_tmp_dev"
```
