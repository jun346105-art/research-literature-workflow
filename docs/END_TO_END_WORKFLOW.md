# End-To-End Workflow

This workflow is local-first after discovery and keeps Zotero and Obsidian under human control.

## 1. Inspect paper-search-pro Results

```powershell
python -m litflow.cli inspect-psp-results --input "<paper-search-pro-result-dir>"
```

- Input: local `paper-search-pro` result directory.
- Output: console inspection report.
- Read-only: yes.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: confirms the result directory is usable.

## 2. Build Candidate Pool

```powershell
python -m litflow.cli build-candidate-pool `
  --input "<paper-search-pro-result-dir>" `
  --output ".\outputs\candidate_pool.json"
```

- Input: `papers.json` or `papers.csv`.
- Output: `candidate_pool.json`.
- Read-only: reads discovery files only.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: review warnings before selection.

## 3. Select Candidates

```powershell
python -m litflow.cli select-candidates `
  --candidates ".\outputs\candidate_pool.json" `
  --out ".\outputs\selected_candidates.json"
```

- Input: `candidate_pool.json`.
- Output: `selected_candidates.json`.
- Read-only: no, writes selection template.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: required. Manually set `"selected": true`.

## 4. Export Zotero Import File

```powershell
python -m litflow.cli export-zotero-import `
  --selected ".\outputs\selected_candidates.json" `
  --format bib `
  --out ".\outputs\selected.bib"
```

- Input: manually edited `selected_candidates.json`.
- Output: `selected.bib` or `selected.ris`.
- Read-only: no, writes import file.
- Modifies Zotero: no. User imports manually.
- Modifies Obsidian: no.
- Human confirmation: required in Zotero after import.

## 5. Read Zotero Collection

```powershell
python -m litflow.cli read-zotero-collection `
  --collection "Collection Name" `
  --output ".\outputs\zotero_collection.json"
```

- Input: Zotero collection name.
- Output: `zotero_collection.json`.
- Read-only: yes.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: check item count and metadata quality.

## 6. Create Obsidian Inbox Notes

```powershell
python -m litflow.cli make-obsidian-notes `
  --items ".\outputs\zotero_collection.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview"
```

- Input: Zotero snapshot.
- Output: empty Obsidian literature note templates.
- Read-only: no.
- Modifies Zotero: no.
- Modifies Obsidian: yes, creates inbox notes only.
- Human confirmation: required before moving notes to formal folders.

## 7. Build Reading Context

```powershell
python -m litflow.cli build-reading-context `
  --items ".\outputs\zotero_collection.json" `
  --out-dir ".\outputs\reading_context" `
  --manifest ".\outputs\reading_context_manifest.json"
```

- Input: Zotero snapshot with PDF attachment paths.
- Output: per-paper raw reading context and manifest.
- Read-only: reads local PDFs and Zotero annotations.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: inspect missing PDF and extraction warnings.

## 8. Clean Reading Context

```powershell
python -m litflow.cli clean-reading-context `
  --context-dir ".\outputs\reading_context" `
  --manifest ".\outputs\reading_context_manifest.json" `
  --out-dir ".\outputs\clean_reading_context" `
  --out-manifest ".\outputs\clean_reading_context_manifest.json" `
  --chunk-size 3500 `
  --overlap 400
```

- Input: raw reading context.
- Output: cleaned context chunks and manifest.
- Read-only: reads generated context.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: review chunking and warnings when needed.

## 9. Audit Clean Context

```powershell
python -m litflow.cli audit-clean-context `
  --clean-dir ".\outputs\clean_reading_context" `
  --manifest ".\outputs\clean_reading_context_manifest.json" `
  --out ".\outputs\clean_context_quality_report.json"
```

- Input: clean context directory and manifest.
- Output: quality gate report.
- Read-only: yes.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: only `ready_for_llm` items should proceed.

## 10. Read One Paper With LLM

```powershell
python -m litflow.cli read-paper-with-llm `
  --clean-context ".\outputs\clean_reading_context\PAPER.json" `
  --out ".\outputs\structured_reading_notes\PAPER.json"
```

- Input: one clean context JSON.
- Output: one structured reading note JSON.
- Read-only: reads context, calls configured LLM.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: required. Validate evidence before applying.

## 11. Preview Obsidian Update

```powershell
python -m litflow.cli preview-obsidian-update `
  --structured-note ".\outputs\structured_reading_notes\PAPER.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview" `
  --out ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --manifest ".\outputs\obsidian_update_preview_manifest.json"
```

- Input: structured reading note JSON and Obsidian inbox.
- Output: reviewable preview Markdown and manifest.
- Read-only: reads target note frontmatter only.
- Modifies Zotero: no.
- Modifies Obsidian: no.
- Human confirmation: required before apply.

## 12. Apply Approved Obsidian Update

Dry-run:

```powershell
python -m litflow.cli apply-obsidian-update `
  --preview ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --target "<ObsidianVault>\00_Inbox\LiteratureReview\@zotero_KEY.md" `
  --manifest ".\outputs\obsidian_update_apply_manifest.json" `
  --dry-run
```

Apply:

```powershell
python -m litflow.cli apply-obsidian-update `
  --preview ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --target "<ObsidianVault>\00_Inbox\LiteratureReview\@zotero_KEY.md" `
  --manifest ".\outputs\obsidian_update_apply_manifest.json" `
  --approved
```

- Input: approved preview and explicit target note.
- Output: backup and apply manifest.
- Read-only: dry-run only.
- Modifies Zotero: no.
- Modifies Obsidian: yes, only with `--approved`.
- Human confirmation: required. The command refuses to write without `--approved`.
