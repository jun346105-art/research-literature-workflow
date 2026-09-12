# Retrieval Quality R1

This is a small, review-gated 48-query retrieval quality package over the frozen `rag_bm25_v1` corpus (10 papers, 185 passages).

- Development: 20 canonical `reviewed` records migrated from the immutable author-reviewed qrels. The original review status, source path, and source-record hash remain attached as provenance; the historical file is unchanged.
- Development hard negatives: 12 new candidate queries, all `pending_review`.
- Held-out: 16 new candidate queries: 8 single-paper answerable, 4 cross-paper answerable, 2 in-domain no-answer, and 2 near-miss hard negatives. All are `pending_review`.

The formal evaluator refuses pending records. Development hard negatives also remain unusable until reviewed. Held-out records are never accepted as tuning input for Top-K, BM25 parameters, RRF parameters, thresholds, or gates. Recall is binary over qrel passage IDs, MRR is binary, and nDCG uses optional positive integer relevance grades (default `1`). For no-answer records, any returned item in the first 10 is counted as a false positive. This batch creates the data and evaluator only; it does not run a formal R1 benchmark or call a Provider.

SHA-256 digests are canonical lowercase hex. Historical corpus/source files retain their raw-byte hashes. New JSON package hashes use sorted compact UTF-8 JSON, and the review CSV hash uses UTF-8 without BOM with LF-normalized line endings, so Git's Windows line-ending conversion cannot change package identity.

Files:

- `r1_dataset.manifest.json`: corpus identity and split/source manifest.
- `passage_hashes.json`: frozen passage/source/text identity for all 185 passages.
- `reviewed_records.json`: canonical R1 copy of the 20 historical reviewed records, with immutable provenance.
- `schemas/query.schema.json`: query/qrel record contract.
- `schemas/result.schema.json`: ranked result contract.
- `schemas/dataset.schema.json`: dataset manifest contract.
- `pending_candidates.json`: 28 candidate records for author review.
- `pending_candidates.review.csv`: review worksheet; no row is ground truth until `answerable_correct`, `relevant_passages_correct`, `review_decision`, `reviewer`, and `reviewed_at` are completed and a separate reviewed artifact is frozen.
