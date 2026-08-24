# Minimal FastAPI Wrapper and Local MVP

`litflow_api` exposes a small HTTP wrapper around the existing CLI-safe workflow.

It is intentionally minimal:

- no user system;
- no database;
- no background queue;
- no Obsidian apply endpoint.

The goal is to show how the local pipeline can be served through backend APIs while preserving the existing safety boundaries.

The M5 browser MVP is localhost-only. It exposes frozen corpus and review artifacts in offline demo mode, which never constructs an LLM client. Online QA requires an explicit service-mode opt-in and a separately authorized call.

## Run

```powershell
$env:PYTHONPATH = "src"
uvicorn litflow_api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

The browser MVP is available at `http://127.0.0.1:8000/`. For an online QA run, set `LITFLOW_ONLINE_QA=1` in the launching process. The service accepts only the frozen `deepseek-v4-flash` deployment model and does not expose credentials, prompts, qrels, or local absolute paths.

## M5 endpoints

- `GET /api/v1/health`: version, demo mode, and frozen corpus identity.
- `GET /api/v1/papers`: public demo-corpus metadata only.
- `POST /api/v1/retrieve`: language routing and frozen BM25 Top-10. It never returns qrels or gold evidence.
- `POST /api/v1/qa/jobs`, `GET /api/v1/jobs/{job_id}`, `GET /api/v1/jobs/{job_id}/events`, and `GET /api/v1/jobs/{job_id}/result`: file-backed, single-execution QA job status and SSE progress.
- `GET /api/v1/passages/{passage_id}`: page-provenanced passage text and optional quote-anchor verification.
- `GET /api/v1/evidence-matrix/demo` and `GET /api/v1/writing/demo`: frozen, read-only review artifacts. The writing endpoint always reports `author_reviewed=true` and `publication_ready=false`.

Only answers that pass canonical schema, entity binding, Top-10 citation membership, and strict quote grounding are displayed. Provider, parse, schema, citation, or quote failures return a safe execution failure rather than an unsupported answer.

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
  "title": "Sample Paper Title",
  "research_context": "Optional project-specific research background."
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
