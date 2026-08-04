# Concepts

## Reading Context

A per-paper JSON file built from Zotero metadata, local PDF text, and Zotero notes or annotations.

It preserves page-level text and warnings before any LLM step.

## Clean Context

A cleaned version of reading context. The cleaner is intentionally conservative:

- normalize line endings;
- repair simple hyphenated line breaks;
- collapse excessive blank lines;
- keep source text close to the PDF extraction.

## Chunk

A chunk is a character-window slice of cleaned paper text.

Default settings:

```text
chunk_size_chars = 3500
chunk_overlap_chars = 400
```

Each chunk stores:

- `chunk_id`
- `page_start`
- `page_end`
- `section_guess`
- `source_page_numbers`
- `text`

## Quality Gate

The quality gate checks whether a clean context is ready for LLM reading.

It flags:

- empty extracted text;
- missing chunks;
- short text;
- incomplete `max_pages` smoke-test outputs;
- all-unknown sections;
- high references ratio;
- annotation alignment problems.

## Evidence Candidate Bank

An evidence candidate bank is produced by chunk-constrained extraction.

The program gives the LLM one chunk at a time. The LLM returns:

```json
{
  "claim": "",
  "quote_hint": "",
  "evidence_type": "method"
}
```

The program fills:

- `chunk_id`
- `page_start`
- `page_end`

Then it anchors `quote_hint` inside the current chunk and extracts exact `evidence_text`.

## Strict Evidence Validation

Final evidence must satisfy:

```python
evidence_text in chunk_text
```

The validator also checks:

- the cited `chunk_id` exists;
- `page_start` / `page_end` match the chunk;
- evidence text does not secretly belong to another chunk.

## Structured Reading Note

A JSON model for structured paper reading. It includes:

- summary;
- background;
- gap;
- contribution;
- method;
- experiments;
- limitations;
- relevance to the user's research;
- evidence links.

## Preview / Apply

Preview creates Markdown for human review.

Apply writes only inside:

```markdown
<!-- LITFLOW_STRUCTURED_READING_START -->
...
<!-- LITFLOW_STRUCTURED_READING_END -->
```

Apply requires `--approved` and creates a backup first.
