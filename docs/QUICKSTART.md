# Quickstart

This guide uses sanitized sample data. It does not require Zotero, real PDFs, a real Obsidian vault, or an LLM API key.

## 1. Run The Sample Preview

```powershell
cd "<repo>"
$env:PYTHONPATH = "src"

python -m litflow.cli preview-obsidian-update `
  --structured-note ".\examples\structured_reading_notes\SAMPLE001_structured_reading_note.json" `
  --vault ".\examples\obsidian_vault" `
  --inbox "00_Inbox/LiteratureReview" `
  --out ".\examples_output\SAMPLE001_preview.md" `
  --manifest ".\examples_output\SAMPLE001_preview_manifest.json"
```

Expected output:

```text
examples_output/SAMPLE001_preview.md
examples_output/SAMPLE001_preview_manifest.json
```

Reference output:

```text
examples/expected_outputs/SAMPLE001_preview.md
```

## 2. Inspect The Evidence Contract

Open:

```text
examples/clean_context/SAMPLE001.json
examples/structured_reading_notes/SAMPLE001_structured_reading_note.json
```

Each `evidence_text` in the structured note is an exact substring of the cited chunk.

## 3. Run With Your Own Zotero Snapshot

After importing selected papers into Zotero manually:

```powershell
python -m litflow.cli read-zotero-collection `
  --collection "Your Collection" `
  --output ".\outputs\zotero_collection.json"
```

Then create Obsidian inbox templates:

```powershell
python -m litflow.cli make-obsidian-notes `
  --items ".\outputs\zotero_collection.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview"
```

## 4. Build Reading Context

```powershell
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
```

## 5. Build Anchored Notes

```powershell
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
```

## 6. Preview Before Apply

```powershell
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
