# Architecture

`research-literature-workflow` is a local-first literature workflow for evidence-grounded paper reading. It connects existing tools instead of replacing them.

## Tool Boundaries

- `paper-search-pro`: discovery layer. It searches online sources and exports result files.
- Zotero: authoritative bibliographic metadata, PDF attachment, annotation, and citation-key source.
- Obsidian: local Markdown knowledge base and review workspace.
- LLM: structured reading assistant, not a source of truth.
- `litflow`: local automation glue around files, validation, previews, and safe apply.

## Local-First Design

Only discovery and LLM calls are online. Core state lives locally:

```text
paper-search-pro output files
Zotero collection snapshot
local PDF attachment paths
Obsidian Markdown vault
JSON manifests and reports
```

`litflow` does not write Zotero, edit Zotero SQLite, download PDFs, or promote notes into formal Obsidian folders.

## Phase Map

| Phase | Input | Output | External writes |
| --- | --- | --- | --- |
| 1A/1C | paper-search-pro result dir | `candidate_pool.json`, inspection report | no |
| 1B | candidate pool | `selected_candidates.json`, BibTeX/RIS export | no |
| 2A | Zotero collection | `zotero_collection.json` | no, read-only Zotero |
| 2B | Zotero snapshot | Obsidian inbox note templates | creates new inbox notes |
| 2C/2D | Zotero snapshot + inbox notes | citation diagnostics, migration plan | no |
| 3A | Zotero snapshot | per-paper `reading_context/*.json` | no |
| 3B | reading context | `clean_reading_context/*.json` | no |
| 3C | clean context | quality gate report | no |
| 4A | clean context | structured reading note JSON | LLM call only |
| 4B | structured note | Obsidian update preview | no |
| 4C | approved preview | marker-region update + backup | one approved Obsidian note |
| 5G+ | clean chunks | evidence candidate bank | LLM calls only |
| 5H+ | evidence bank | anchored structured note + preview | no |

## PDF And Chunk Pipeline

PDFs are read locally with `pypdf`.

1. Extract text page by page.
2. Preserve `page_number`, text, and `char_count`.
3. Record warnings for missing PDFs, empty pages, encrypted files, and extraction failures.
4. Clean lightly: normalize line endings, repair simple hyphenated line breaks, collapse excessive blank lines.
5. Guess sections using simple heading regexes.
6. Join non-empty pages and chunk by character windows.

Default chunk settings:

```text
chunk_size_chars = 3500
chunk_overlap_chars = 400
```

Each chunk stores:

- `chunk_id`
- `page_start`
- `page_end`
- `source_page_numbers`
- `section_guess`
- `text`

## Evidence Validation

Final evidence links must contain:

- `claim`
- `chunk_id`
- `page_start`
- `page_end`
- `evidence_text`

Strict validation requires:

```python
evidence_text in chunk_text
```

It also checks that the chunk exists and that `page_start` / `page_end` match the cited chunk. Wrong chunk IDs, missing evidence text, and page mismatches are reported separately.

## Anchored Evidence Pipeline

The anchored pipeline was added after the initial v0.1 workflow because direct LLM evidence generation was unstable.

Old approach:

```text
multi-chunk prompt
-> LLM chooses chunk_id and writes evidence_text
-> risk: normalized quote, wrong chunk_id, page mismatch
```

Current approach:

```text
one chunk per LLM call
-> LLM returns claim + quote_hint only
-> program fills chunk_id and page range
-> program anchors quote_hint inside that chunk
-> program extracts exact evidence_text from chunk_text
-> strict validation
-> candidate bank
-> LLM selects candidate_id values
-> program assembles final evidence_links
```

This keeps the final `evidence_text`, `chunk_id`, and page range under program control.

## Human-In-The-Loop

Human review is required because literature knowledge bases are durable assets:

- Candidate discovery can be noisy.
- Zotero metadata should remain authoritative.
- PDF extraction can be incomplete.
- LLM output can be plausible but unsupported.
- Obsidian should not be polluted by unreviewed generated text.

The workflow uses manual gates before Zotero import, before Obsidian apply, and before any future promotion into formal folders.

## Current Scope

Supported:

- Local candidate ingestion from paper-search-pro output.
- Manual selection and BibTeX/RIS export.
- Read-only Zotero snapshots.
- Obsidian inbox note templates.
- Local PDF extraction and clean context generation.
- Quality gate for LLM readiness.
- Evidence-bank grounded structured reading.
- Reviewable Obsidian preview.
- Approved marker-region apply with backup.

Not supported:

- Hosted multi-user service.
- Automatic PDF download.
- OCR.
- Automatic literature review generation.
- Direct Zotero writes.
- Automatic Obsidian promotion.
- Perfect section detection.
