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

Summary:

- 50 discovery candidates were screened down to 8 selected papers.
- 8 papers were read from Zotero and processed into PDF reading contexts.
- 8 clean contexts passed the quality gate.
- 4 papers went through anchored evidence note generation.
- 4 Obsidian previews were created.
- 1 preview was manually approved and applied into an Obsidian marker region.
- Test suite: 101 passed.

## Dogfood Run 001

After the initial small-batch acceptance, the workflow was tested again on two additional papers that had not gone through anchored final note generation.

Summary:

- 2 new papers were tested after the main acceptance run.
- Both produced evidence candidate banks, anchored final notes, and Obsidian previews.
- Strict evidence validation found 0 final evidence failures.
- 1 preview needed deterministic wording polish before apply.
- 1 preview was manually approved and applied after dry-run and backup.

The dogfood run is documented in [DOGFOOD_RUN_001.md](DOGFOOD_RUN_001.md). It is intentionally small: the point is to verify that the system works on new local papers without turning the repository into a dump of private outputs.

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

More details: [Evidence Grounding](EVIDENCE_GROUNDING.md).

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
