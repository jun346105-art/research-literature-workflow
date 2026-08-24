# LitFlow Resume Project Description

## One Line

Built LitFlow, a local-first, evidence-grounded bilingual research writing copilot for engineering literature that turns local papers into reviewable QA, Evidence Matrix, and author-editable draft material with passage-level citations and quote validation.

## Three Resume Bullets

- Built a local evidence chain spanning PDF Clean Context, page-provenanced passages, language-aware BM25 retrieval, strict claim/citation/quote validation, and human review.
- Improved Chinese-query retrieval from BM25-ZH-raw Recall@10 `0.6275` to machine-translation -> BM25-EN `0.7157` on a 20-query human-reviewed pilot; displayed answers had 100% citation validity, strict quote grounding, and claim coverage.
- Delivered FastAPI/SSE, a native evidence workbench, persisted jobs, Evidence Inspector, Evidence Matrix, bilingual author-editable drafts, and a non-root localhost-only Docker Offline Demo.

## Detailed Bullets

- Used Python, FastAPI, Pydantic, BM25, and Docker to ship a local research-writing MVP.
- Implemented a shared span mapper that rejects cross-passage, cross-paper, non-contiguous, and rewritten quotes.
- Added partial-answer and entity-binding contracts to prevent cross-paper method attribution.
- Preserved raw response, usage, latency, manifest, SHA, and validation failures as auditable artifacts.
- Converted human-reviewed claims into an Evidence Matrix and a bilingual method-comparison draft marked `publication_ready=false`.

## LLM Application Engineering Skills

- Structured LLM output validation
- Retrieval evaluation and qrels governance
- Evidence provenance and deterministic anchoring
- FastAPI/SSE and file-backed job lifecycle
- Docker delivery and local security boundaries
- Human-in-the-loop quality evaluation

## Recommended Wording

Use bounded claims such as “small human-reviewed pilot,” “9/17 grounded answer success,” and “9/9 displayed answers author-reviewed as usable.”

## Avoid

- “Production-ready SaaS”
- “Eliminated hallucinations”
- “Answers every question accurately”
- “Large-scale SOTA benchmark”
- “Automatically generates publication-ready papers”
