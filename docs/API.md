# Minimal FastAPI Wrapper

`litflow_api` exposes a small HTTP wrapper around the existing CLI-safe workflow.

It is intentionally minimal:

- no user system;
- no database;
- no background queue;
- no Obsidian apply endpoint.

The goal is to show how the local pipeline can be served through backend APIs while preserving the existing safety boundaries.

## Run

```powershell
$env:PYTHONPATH = "src"
uvicorn litflow_api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

### `GET /health`

Returns:

```json
{"status": "ok"}
```

### `POST /evidence-candidate-bank`

Builds a chunk-constrained evidence candidate bank.

```json
{
  "clean_context": "outputs/clean_reading_context/PAPER.json",
  "out": "outputs/evidence_candidate_banks/PAPER_evidence_candidates.json",
  "report": "outputs/evidence_candidate_banks/PAPER_evidence_candidates_report.json"
}
```

### `POST /structured-note-from-bank`

Generates a structured reading note from an evidence candidate bank.

```json
{
  "candidate_bank": "outputs/evidence_candidate_banks/PAPER_evidence_candidates.json",
  "clean_context": "outputs/clean_reading_context/PAPER.json",
  "out": "outputs/structured_reading_notes/PAPER_anchored_final.json",
  "zotero_key": "PAPER",
  "citation_key": "paper2026sample",
  "title": "Sample Paper Title"
}
```

### `POST /preview-obsidian-update`

Generates a reviewable Obsidian update preview.

```json
{
  "structured_note": "outputs/structured_reading_notes/PAPER_anchored_final.json",
  "vault": "D:/path/to/ObsidianVault",
  "inbox": "00_Inbox/LiteratureReview",
  "out": "outputs/obsidian_update_previews/PAPER_preview.md",
  "manifest": "outputs/obsidian_update_preview_manifest.json"
}
```

## Why No Apply Endpoint?

Applying a preview writes to a real Obsidian note. The CLI supports this with `--approved` and backup creation, but the first API wrapper deliberately does not expose it.

This keeps the public API demo focused on safe generation and preview. Apply can be added later with explicit approval, dry-run support, backup checks, and reviewed manifests.
