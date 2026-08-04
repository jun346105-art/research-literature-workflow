# Examples

This directory contains sanitized toy data for understanding the file contracts. It is not real paper text and does not contain private Zotero, PDF, Obsidian, or LLM output.

## Files

- `psp_results/papers.json`: sample paper-search-pro style output.
- `zotero_snapshot/zotero_collection.sample.json`: sample read-only Zotero snapshot.
- `clean_context/SAMPLE001.json`: minimal clean context with two chunks.
- `evidence_candidate_banks/SAMPLE001_evidence_candidates.json`: candidate bank with evidence anchored to chunks.
- `structured_reading_notes/SAMPLE001_structured_reading_note.json`: final structured note where evidence links come from the candidate bank.
- `obsidian_previews/SAMPLE001_preview.md`: preview-only Markdown; not an applied Obsidian note.

## Trust Boundary Demonstrated

Every `evidence_text` in the structured note is a substring of the cited chunk in `clean_context/SAMPLE001.json`.

```text
evidence_text in chunk_text
```

This is the core rule used by the anchored evidence pipeline.
