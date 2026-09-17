# Retrieval Quality R1 Result

Status: `retrieval_quality_r1_complete`.

## Frozen evaluation

- Corpus: 10 papers, 185 passages.
- Reviewed development: 20 historical queries plus 12 reviewed hard negatives (`32` total).
- Held-out: 16 reviewed queries, never used for tuning.
- Evaluation plan: `r1_evaluation_plan.json`.
- Detailed metrics: `results/r1_result.json`.
- Per-query rankings: `results/r1_rankings.json`.
- Provider/API/network cost: zero; model query encoding ran from a local, exact-revision cache with offline mode and `local_files_only=True`.

The predeclared development rule maximized answerable success@10, Recall@10, nDCG@10, and MRR@10 in that order, then minimized no-answer false-positive rate and latency. It selected `bm25_en`. No held-out observation influenced that choice, and held-out was executed once without retry.

## Development comparison

| Mode | Recall@5 | Recall@10 | Recall@20 | MRR@10 | nDCG@10 | Answerable success@10 | No-answer FP@10 | Mean ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25-ZH | 0.509804 | 0.627451 | 0.745098 | 0.381863 | 0.421364 | 0.764706 | 0.733333 | 4.317263 |
| BM25-EN | 0.647059 | 0.735294 | 0.892157 | 0.674020 | 0.642533 | 0.882353 | 1.000000 | 4.675594 |
| Windowed Dense | 0.460784 | 0.519608 | 0.539216 | 0.281373 | 0.329696 | 0.588235 | 1.000000 | 9.683006 |
| Hybrid/RRF | 0.490196 | 0.539216 | 0.627451 | 0.397059 | 0.399771 | 0.647059 | 1.000000 | 14.774794 |

## One-shot held-out result

Selected mode: `bm25_en`.

| Metric | Result |
|---|---:|
| Recall@5 | 0.715278 |
| Recall@10 | 0.840278 |
| Recall@20 | 0.861111 |
| MRR@10 | 0.680556 |
| graded nDCG@10 | 0.688869 |
| Answerable retrieval success@10 | 1.000000 |
| Answerable retrieval success@20 | 1.000000 |
| No-answer false-positive rate@10 | 1.000000 |
| Latency mean / P50 / P95 (ms) | 7.010937 / 7.654100 / 8.323100 |

The answerable result is strong within this small frozen corpus, but the no-answer false-positive rate is `1.0`: every held-out negative received at least one lexical result in the top 10. R1 therefore does **not** validate a relevance/no-answer gate, semantic correctness, open-domain retrieval, or scale.

H007 is only query/claim-held-out. Its passages overlap development, while its answer claim does not (`passage_overlap=true`, `answer_claim_overlap=false`); it is not strict passage-held-out evidence.
