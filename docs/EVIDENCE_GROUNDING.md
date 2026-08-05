# Evidence Grounding

`litflow` treats LLM output as a draft, not as trusted evidence.

The core rule is intentionally simple:

```python
evidence_text in chunk_text
```

Every final evidence snippet saved in a structured reading note must be an exact substring of the source chunk.

## Why This Matters

In real PDF extraction, text often contains line breaks, hyphenation, headers, footers, and OCR-like artifacts. LLMs tend to make that text more readable. That is useful for prose, but unsafe for evidence because the quote may no longer exist in the source text.

Early tests exposed two failure modes:

- the model normalized or rewrote `evidence_text`;
- the model selected a plausible but wrong `chunk_id`.

`litflow` avoids trusting the model for final evidence coordinates.

## Anchored Pipeline

The current anchored path separates model judgment from evidence ownership:

```text
clean chunk
-> LLM proposes claim + quote_hint for this chunk only
-> program fills chunk_id and page range
-> program extracts exact evidence_text from chunk_text
-> LLM selects candidate_id for the final note
-> program maps candidate_id back to exact evidence_text
-> strict validation
```

The LLM does not freely create final `chunk_id`, `page_start`, `page_end`, or `evidence_text`.

## What Is Still Human-Reviewed

Strict grounding proves that a quote exists in the source chunk. It does not prove that:

- the claim is the best interpretation of the quote;
- the generated Chinese note is publication-ready;
- the paper is relevant enough to cite;
- the evidence is sufficient for a thesis argument.

That is why `litflow` keeps the workflow preview-first and requires manual approval before writing to Obsidian.
