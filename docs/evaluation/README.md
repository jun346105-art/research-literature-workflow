# Evaluation methodology and failure analysis

[Documentation](../README.md) · [English homepage](../../README.md) · [中文首页](../../README.zh-CN.md)

## Frozen design / 冻结设计

R1 evaluates retrieval over **10 papers and 185 passages**, with **32 development queries (17 answerable, 15 no-answer)** and **16 held-out queries (12 answerable, 4 no-answer)**. The predeclared development selection rule chose `bm25_en`; held-out ran once, without retry or tuning. Answerable success@10 means that retrieval finds at least one relevant passage for an answerable query. It is not report-generation success or semantic correctness.

R1 衡量冻结语料中的证据检索。32 条 development 用于选择检索模式；16 条 held-out 只运行一次，未参与调参。Answerable success 指检索命中相关证据，不代表报告回答正确。

Sources: [formal result JSON](../deep_research/retrieval_quality_r1/results/r1_result.json), [evaluation plan](../deep_research/retrieval_quality_r1/r1_evaluation_plan.json), [dataset manifest](../deep_research/retrieval_quality_r1/r1_dataset.manifest.json), [result/hash manifest](../deep_research/retrieval_quality_r1/results/r1_result_manifest.json), [per-query rankings](../deep_research/retrieval_quality_r1/results/r1_rankings.json).

## Full results / 完整结果

| BM25-EN metric | Development | Held-out |
|---|---:|---:|
| Recall@5 | 0.647059 | 0.715278 |
| Recall@10 | 0.735294 | 0.840278 |
| Recall@20 | 0.892157 | 0.861111 |
| MRR@10 | 0.674020 | 0.680556 |
| nDCG@10 | 0.642533 | 0.688869 |
| Answerable retrieval success@10 | 0.882353 | 1.000000 |
| No-answer false-positive rate@10 | 1.000000 | 1.000000 |

The homepage rounds held-out Recall@10 to 84.0%, nDCG@10 to 68.9% and answerable success@10 to 100%. [R1_RESULT](../deep_research/retrieval_quality_r1/R1_RESULT.md) retains the complete mode comparison and latency measurements.

## Failure analysis / 失败分析

- **No-answer retrieval remains weak.** All four held-out negatives received a lexical result in the top 10: no-answer FP@10 is 1.0. High answerable recall does not imply reliable abstention.
- **The threshold is development-only.** A later threshold of `11.398627187607` reduced development FP@10 from 1.0 to 0.8, removing **3 of 15** false positives while preserving answerable success@10 at 0.882353. Twelve negatives still return false positives. The original held-out result was already observed and was not rerun; this is not an independently validated held-out improvement. See the [threshold design and limitations](../deep_research/retrieval_quality_r1/ROUND4_RELEVANCE_GATE.md) and [machine-readable result](../deep_research/retrieval_quality_r1/round4_relevance_gate.json).
- **Wrong attribution can score highly.** Negative questions may contain real corpus terms while asserting the wrong relationship. A lexical threshold does not verify those relationships.
- **H007 is query/claim-held-out only.** Its passages overlap development; its answer claim does not. It is not strict passage-held-out evidence.
- **Scope is bounded.** These results do not establish semantic correctness, publication quality, open-domain retrieval or performance at scale. Deterministic quote anchoring and human semantic review answer different questions.

Held-out 的 4 条无答案查询均出现词法误召回。后续阈值仅在 development 上减少 3/15 个误召回，仍有 12/15 未解决；没有独立 held-out 改善结论。H007 的 passage 与 development 重叠，不能称为严格 passage-held-out。完整失败记录保留原样。

## Reproduction and earlier evaluations

The [R1 package guide](../deep_research/retrieval_quality_r1/README.md) describes the frozen review/evaluation inputs. [Dependency reproducibility](../deep_research/DEPENDENCY_REPRODUCIBILITY.md) covers runtime, test and optional local model dependencies. Private corpus/model assets remain outside Git; the public result manifests support auditing, but do not distribute a complete reproduction corpus. This documentation cleanup does not rerun or alter the formal evaluation.

- Earlier acceptance metrics: [English](../EVALUATION.md) / [中文](../EVALUATION.zh-CN.md).
- Development pilot: [Run 002 English](../EVALUATION_RUN_002.md) / [Run 002 中文](../EVALUATION_RUN_002.zh-CN.md).
- Earlier evidence: [Dogfood Run 001](../DOGFOOD_RUN_001.md), [batch E2E acceptance](../V0_1_BATCH_E2E_ACCEPTANCE_TEST.md), [M8 protocol](../M8B_EVALUATION_PROTOCOL.zh-CN.md).
- Report pilots: [single-paper](../deep_research/REAL_SINGLE_PAPER_E2E_RESULT_V1.md), [cross-paper](../deep_research/CROSS_PAPER_COMPARISON_RESULT_V1.md), [insufficient evidence](../deep_research/INSUFFICIENT_EVIDENCE_RESULT_V1.md).
- Review history: [pending review packet](../deep_research/retrieval_quality_r1/PENDING_REVIEW_PACKET.md); the reviewed records and final results remain authoritative.
