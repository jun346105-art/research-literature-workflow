# Retrieval Quality R1 — Round 4 Relevance Gate

Status: `implemented_development_calibrated_not_independently_validated`.

## Design

Round 4 implements exactly one targeted optimization after the frozen R1 baseline: a deterministic threshold on the selected BM25-EN ranking's top score.

- Calibration input: the 32 development records only.
- Constraint: answerable retrieval success@10 must remain at least `0.85`.
- Objective: minimize development no-answer false-positive rate, then preserve answerable success, Recall@10, and nDCG@10.
- Selected threshold: `11.398627187607`.
- At or above the threshold: preserve the original ranking unchanged.
- Below the threshold: return an empty result as a safe retrieval abstention.
- No Reranker, Query Rewrite, Dense change, additional model, Provider, or network call.

## Development outcome

| Metric | Baseline | With gate |
|---|---:|---:|
| Answerable success@10 | 0.882353 | 0.882353 |
| No-answer false-positive rate@10 | 1.000000 | 0.800000 |
| Recall@10 | 0.735294 | 0.735294 |
| nDCG@10 | 0.642533 | 0.642533 |

The gate removes 3 of 15 development false positives without removing any already-successful answerable query. The improvement is limited: 12 of 15 development negatives remain false positives because wrong-attribution questions can still contain real, high-scoring corpus terms.

## Evidence boundary

The original 16-query held-out result is immutable and was not rerun, replayed, or used to select the threshold. Because that held-out result was already observed before Round 4, this change does not claim an independent held-out improvement. It is an implemented development-calibrated safeguard, not evidence that retrieval abstention is solved.

The next escalation, if ever authorized, would require a new untouched evaluation set or a semantic relation verifier. Round 4 deliberately stops before either expansion.
