# Evaluation Run 002：开发集试验

## 范围

Evaluation Run 002 是覆盖 3 篇论文的 development pilot。它不是 held-out benchmark，也不是独立盲审专家评估。Baseline 与 Proposed 的 claims 没有逐条配对，因此其数量不应被解释为配对统计比较。

私有 source artifacts 未纳入本仓库，因为其中可能包含本机路径、受版权保护的 PDF 文本和人工审核材料。本公开报告来自经过核验的 private canonical aggregate。其 aggregate summary SHA-256 为 `abf5626e1afac5bff70691bc0e1693f9643d1d83377ede1264e519783b64d087`。SHA-256 用于标识 run 与 artifact integrity；它本身并不使结果可公开复现。缺少私有 frozen inputs 时，外部读者无法完整复现真实结果。

## 方法

两条路径使用相同的 frozen paper inputs 与 research context。

- **Baseline** 使用 `raw-baseline-multichunk-v2` 与内容契约 `raw-baseline-content-v1`，从多个 chunks 生成 claims 和 evidence fields。Baseline evidence 在评分前不经过 anchoring、repair、删除或重写。
- **Proposed** 使用 `chunk-constrained-evidence-v1`，再使用 `evidence-bank-note-v1`：模型逐 chunk 提出短 quote hints；程序锚定连续的 source substring；final note 只选择已 anchored 的 candidates；最终 evidence 通过 strict exact validation。

system-owned metadata，包括 Zotero key、citation key 和 title，来自 frozen manifest。model-generated content 包括 summaries、claims、quote hints 与 candidate selections。程序拥有 candidate identifiers、chunk/page provenance 与最终 `evidence_text`；不信任模型直接复刻最终 quotations。

Baseline 共 3 次调用。Proposed 共 62 次调用，即 59 次 candidate 调用与 3 次 final-note 调用。这不是 equal-call、equal-token、equal-cost 或 equal-latency comparison；比较目标是两种 pipeline architecture 的 evidence traceability。Proposed 以更细粒度的调用换取可验证证据，这是工程取舍。

## 可复现性

| 项目 | 数值 |
| --- | --- |
| LLM run Git SHA | `55754efb67dfa157865a9ed47098c4f058d3b821` |
| Public aggregation Git SHA | `d4cb25676f799bdf13bff7952fab610b52bf0703` |
| Model | `deepseek-v4-flash` |
| Temperature | `0` |
| Thinking | disabled |
| Response format | JSON object |
| Calls | 65，0 retries，0 runner errors |
| Provider-reported usage | 65 / 65 calls |
| Input / output tokens | 128009 / 19778 |
| Reference cost | 0.167565 CNY |

成本是在固定假设价格下的参考估算：每百万 input tokens 为 1 CNY，每百万 output tokens 为 2 CNY。它不是 provider invoice。`chars_div_4` 仅用于 context guard 估算，不是模型 tokenizer，也不是测得的 token count。

## 结果

| 指标 | Baseline | Proposed |
| --- | ---: | ---: |
| Final evidence links | 23 | 37 |
| Strict exact grounding | 1 / 23 | 37 / 37 |
| Fully supported | 17 / 23 (73.9%) | 32 / 37 (86.5%) |
| Supported + partially supported | 23 / 23 (100%) | 36 / 37 (97.3%) |
| Accept | 16 / 23 (69.6%) | 26 / 37 (70.3%) |
| Revise | 7 / 23 (30.4%) | 10 / 37 (27.0%) |
| Reject | 0 / 23 (0%) | 1 / 37 (2.7%) |

本轮处理了 3 篇论文和 59 个 chunks。Proposed candidate 阶段产生 100 个 candidates：57 个 anchored，43 个 failed。包含 candidate 的 chunk coverage 为 35 / 59。成功 anchors 包括 13 个 exact matches 与 44 个 normalized-whitespace matches。失败包括 40 个 anchor-not-found 和 3 个 ambiguous anchors。

latency 使用 aggregate 的 nearest-rank 统计：65 次调用的 overall p50/p95 为 2662.303 / 14512.357 ms。Baseline p50/p95 为 14455.197 / 18973.838 ms；candidate p50/p95 为 2591.414 / 3501.804 ms；final-note p50/p95 为 22309.764 / 22777.794 ms。

## 解释

核心结果是 evidence traceability 与 strict exact grounding 的改善，而不是宣称通用准确率提升。从 1 / 23 到 37 / 37 的 strict grounding 表明，在本 pipeline 下，Proposed final evidence strings 可追溯到其声明的 chunks。

Strict grounding 不证明 claim 在语义上正确，不代表消除 hallucination，也不构成通用 accuracy rate。Baseline evidence 虽常常未通过 strict grounding，但人工审核仍判断其内容通常至少部分有依据。反过来，Proposed evidence 仍有 1 条 unsupported，并有多条需要 revise，因此 human review 仍然必要。

两条路径的人工 acceptance rate 基本相当。因此本 pilot 没有证明语义质量大幅提升；最明确的结果是 strict evidence traceability。Candidate chunk coverage 也不等于 retrieval recall：未产生 anchored candidate 的 chunk 并不自动代表不相关或错误。

## 已知限制

- 样本只有 3 篇论文，属于 development pilot。
- 标签由项目作者在 AI-assisted translation 下完成，不是独立盲审专家标注。
- Baseline 与 Proposed 的 evidence 数量不同，claims 未逐条配对。
- Candidate anchoring 成功率为 57 / 100。
- PDF 抽取可能含有 NUL-like artifacts、异常断词、重复页眉和其他文本噪声。
- 历史 reviewer notes 存在不可逆编码损失。固定审核标签仍完整，但 notes 不参与指标，也不公开。
- 本报告不公开 PDF excerpts、API information、本机路径或 Zotero storage paths。

## 下一阶段

下一阶段计划为 **v0.2.1 PDF Cleaning, Chunking, and Candidate Anchoring Hardening**。

- 对 43 条 anchoring failures 进行确定性分类。
- 清理 Unicode、NUL-like artifacts、断词、换行、页眉、页脚与重复文本。
- 对比 fixed-character、token-aware 与 sentence/section-aware chunking。
- 记录 chunk size、overlap、section 和 page provenance。
- 在 development set 上调参，同时保留新的 held-out samples。
- 完成 hardening 后运行 Evaluation Run 003。

当前阶段不开始 Vector DB、RAG、Agent 或 VLM 实现。
