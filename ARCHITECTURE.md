# Architecture

`research-literature-workflow` is a local-first research literature workflow connecting `paper-search-pro`, Zotero, Obsidian, and OpenAI-compatible LLMs for structured, evidence-grounded paper reading.

中文定位：一个本地优先的科研文献工作流工具，用于连接 paper-search-pro、Zotero、Obsidian 与兼容 OpenAI API 的大模型，实现可审计、可人工确认的结构化文献精读。

## System Boundary

`litflow` is glue code. It does not replace the tools around it:

- `paper-search-pro`: online discovery layer. It searches literature and exports result files.
- Zotero: formal bibliographic database, PDF attachment manager, annotation source, citation key source.
- Obsidian: local Markdown knowledge base and review workspace.
- LLM: optional single-paper structured reading assistant.
- Human reviewer: final authority for selection, import, note updates, and knowledge-base promotion.

## Local-First / Online Discovery

The only expected online discovery step is outside `litflow`: the local `paper-search-pro` skill queries academic sources and writes files such as `papers.json`, `papers.csv`, `papers.bib`, `papers.ris`, and reports.

After discovery, the workflow is local-first:

1. Candidate files are normalized locally.
2. Selection is manual.
3. Zotero is read through a local read-only layer.
4. PDFs are read from local attachment paths.
5. Obsidian notes are updated only after preview approval.

## Phase Inputs And Outputs

| Phase | Input | Output | Writes external tools? |
| --- | --- | --- | --- |
| 0 | local paths | project/vault layout plan | no |
| 1A | `papers.json` / `papers.csv` | `candidate_pool.json` | no |
| 1B | `candidate_pool.json` | `selected_candidates.json`, `selected.bib`, `selected.ris` | no |
| 1C | paper-search-pro result dir | inspection report | no |
| 2A | Zotero collection | `zotero_collection.json` | no, read-only Zotero |
| 2B | `zotero_collection.json` | empty Obsidian inbox notes | yes, creates inbox templates only |
| 2C | Zotero collection / inbox notes | citation diagnostics, note check report | no |
| 2D | Zotero snapshot / inbox notes | migration plan | no |
| 3A | Zotero snapshot | per-paper `reading_context/*.json` | no |
| 3B | reading context | `clean_reading_context/*.json` | no |
| 3C | clean context | quality gate report | no |
| 4A-mini | one clean context | one `structured_reading_note.json` | LLM call only |
| 4B | one structured note | one Obsidian update preview | no |
| 4C | approved preview | marker-region update + backup | yes, one approved Obsidian note |

## Human-In-The-Loop

The workflow keeps humans in control because literature management has durable consequences:

- Candidate papers can be noisy.
- Zotero should remain the authoritative metadata source.
- LLM output can be incomplete or wrong.
- Obsidian is the long-term knowledge base and should not be polluted by unreviewed text.

Human confirmation gates exist before Zotero import, before Obsidian writes, and before any future promotion into formal literature folders.

## LLM Output Boundary

LLM output is never written directly into Obsidian. Phase 4A writes structured JSON. Phase 4B converts it into a reviewable preview. Phase 4C requires `--approved`, creates a backup, and writes only inside:

```markdown
<!-- LITFLOW_STRUCTURED_READING_START -->
...
<!-- LITFLOW_STRUCTURED_READING_END -->
```

Frontmatter and marker-external user content are preserved.

## Evidence Links

`StructuredReadingNote.evidence_links` must include:

- `claim`
- `chunk_id`
- `page_start`
- `page_end`
- `evidence_text`

The reader validates that:

- `chunk_id` exists in the input clean context.
- `page_start` / `page_end` match the cited chunk.
- `evidence_text` appears in the cited chunk text.

This keeps structured reading notes traceable to extracted paper text and catches common LLM normalization issues such as fixing broken PDF words.

## v0.1 Scope

Supported:

- Local paper-search-pro result inspection.
- Candidate pool generation from JSON/CSV.
- Manual selection template and BibTeX/RIS export.
- Read-only Zotero collection snapshots.
- Obsidian inbox note template generation.
- Citation key diagnostics and note reconciliation planning.
- Local text PDF extraction with `pypdf`.
- Reading context cleaning, chunking, and quality gate.
- Single-paper LLM structured reading.
- Obsidian update preview and approved marker-region apply.

Not supported:

- Batch LLM close reading.
- Literature review generation.
- Automatic PDF download.
- OCR for scanned PDFs.
- Zotero writes or SQLite edits.
- Automatic Obsidian promotion into formal folders.
- Automatic tag governance.
- Perfect section detection.
- Trusting LLM output without evidence validation and human review.
