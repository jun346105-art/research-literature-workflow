# LitFlow 简历项目描述

## 一句话版本

开发 LitFlow，一个本地优先、证据驱动、双语工科文献研究写作 Copilot，通过 passage 级 citation 与 quote 验证，将本地论文转化为可审核的 QA、Evidence Matrix 和作者可编辑草稿。

## 三条简历 Bullet

- 设计本地文献证据链：PDF Clean Context、带页码 passage corpus、语言感知 BM25、严格 claim/citation/quote validation 和人工审核闭环。
- 在 20-query human-reviewed pilot 中，将中文 query 的 machine translation -> BM25-EN Recall@10 从 `0.6275` 提升到 `0.7157`；展示答案的 citation validity、strict quote grounding 与 claim coverage 均为 `100%`。
- 交付 FastAPI/SSE 原生 UI 和 Docker Offline Demo，支持 persisted job、Evidence Inspector、Evidence Matrix、双语作者可编辑写作草稿；容器默认非 root、只读输入与 localhost-only。

## 五条详细版本

- 使用 Python、FastAPI、Pydantic、BM25 和 Docker 构建本地研究写作 MVP。
- 建立共享 span mapper，拒绝跨 passage、跨 paper、非连续或改写 quote。
- 设计 partial answer 与 entity binding，避免跨论文方法实体错配。
- 将原始 response、usage、latency、manifest、SHA 和失败 artifact 纳入可复现运行边界。
- 将人工审核 Claim 汇总为 Evidence Matrix，并生成 `publication_ready=false` 的双语作者可编辑方法比较草稿。

## LLM 应用开发岗位技能映射

- LLM structured output and validation
- Retrieval evaluation and qrels governance
- Evidence provenance and deterministic text anchoring
- FastAPI/SSE/file-backed job lifecycle
- Docker local delivery and security boundaries
- Human-in-the-loop quality evaluation

## 推荐写法

使用“small human-reviewed pilot”“grounded answer success 9/17”“displayed answers 9/9 author-reviewed as usable”等带分母、带边界的表述。

## 禁止的夸大表述

- “构建 production-ready SaaS”
- “消除了幻觉”
- “所有问题准确回答”
- “大规模 benchmark SOTA”
- “自动生成可投稿论文”
