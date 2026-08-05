# Evaluation And Acceptance Metrics

`litflow` is evaluated as a research workflow system, not as a defect-detection model or a one-shot summarizer.

The project does not report mAP, precision, recall, or summarization accuracy because it does not train a computer-vision model and does not claim that LLM-generated prose is automatically correct.

Instead, the current MVP measures:

- workflow completion;
- source traceability;
- strict evidence grounding;
- safe Obsidian write boundaries;
- repeatable tests.

## Small-Batch E2E Acceptance

The current acceptance run used a real local workflow for the topic:

```text
logistics package defect detection RGB-D geometric verification YOLO
```

| Category | Metric | Result |
| --- | --- | ---: |
| Discovery | candidates_found | 50 |
| Screening | selected_papers | 8 |
| Zotero | zotero_snapshot_items | 8 |
| PDF | pdf_exists_rate | 8 / 8 |
| Context | reading_context_success | 8 / 8 |
| Context | clean_context_success | 8 / 8 |
| Quality Gate | ready_for_llm_rate | 8 / 8 |
| LLM Reading | original_structured_notes | 4 |
| Evidence Pipeline | anchored_candidate_banks | 4 |
| Evidence Pipeline | anchored_final_notes | 4 |
| Preview | anchored_previews_ready | 4 |
| Apply Safety | approved_marker_apply | 1 |
| Tests | pytest | 101 passed |

## Evidence Grounding

The final evidence rule is strict:

```python
evidence_text in chunk_text
```

The LLM is not trusted to produce final quote text. In the anchored pipeline:

1. Each chunk is processed as a constrained evidence source.
2. The LLM proposes a claim and quote hint within that chunk.
3. The program fills `chunk_id`, `page_start`, and `page_end`.
4. The program extracts final `evidence_text` from the original `chunk_text`.
5. The final structured note is accepted only if the evidence text is an exact substring of the source chunk.

## Safety Metrics

| Safety Boundary | Result |
| --- | ---: |
| Zotero writes | 0 |
| Zotero SQLite modifications | 0 |
| automatic PDF downloads | 0 |
| unapproved Obsidian writes | 0 |
| apply without backup | 0 |
| apply outside marker region | 0 |

## What This Proves

The current MVP proves that a small batch of real papers can move through:

```text
discovery -> manual selection -> Zotero snapshot -> PDF context -> clean chunks -> evidence bank -> structured note -> preview -> approved marker apply
```

with strict evidence traceability and explicit human review gates.

## What This Does Not Prove

The current metrics do not prove:

- that LLM prose is objectively perfect;
- that generated notes are ready for citation without human review;
- that scanned PDFs will work without OCR;
- that the system is production-ready as a hosted multi-user service;
- that it can replace Zotero, Obsidian, or a human literature review.

The intended claim is narrower: `litflow` provides a safer, inspectable local workflow for creating evidence-grounded reading notes.
