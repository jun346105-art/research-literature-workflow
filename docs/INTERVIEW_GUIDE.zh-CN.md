# LitFlow 面试讲解指南

## 30 秒介绍

LitFlow 是面向工科文献的本地优先、证据驱动、双语研究写作 Copilot。它将本地 PDF 和 Zotero 元数据转化为带页码与 passage 溯源的研究材料。展示给用户的 QA Claim 必须通过 citation membership、quote grounding 和 claim-citation coverage 验证；证据不足时显式拒答或给出 partial answer。

## 3 分钟介绍

项目先将本地论文抽取为 Clean Context 和带页码 provenance 的 passages。中文问题通过受控机器翻译检索英文 BM25，英文问题保持原文。QA 模型只看到 Top-10 passages，程序验证每条 claim 的 citation、论文实体归属和连续英文 quote。

通过后，结果进入本地 FastAPI/SSE/UI。用户可从 Claim 跳到 Evidence Inspector，查看论文、页码、passage、quote 和完整上下文。经过人工审核的 QA Claim 还能形成 Evidence Matrix 和双语作者可编辑草稿。Docker 默认离线，只显式开启 Online QA。

## 10 分钟技术讲解

1. **输入和 provenance**：PDF 文本按页抽取、清洗、chunk，并保留 `chunk_id`、页码和 section 线索。
2. **检索**：固定 10 篇、185 passages 的 pilot corpus。中文 query 使用 machine translation -> BM25-EN，英文 query 使用原 query -> BM25-EN。
3. **QA contract**：模型输出严格 JSON；程序拥有 citation passage、页码和最终 evidence quote 的验证权。
4. **验证**：citation 必须来自 Top-10；citation paper 与 subject paper 一致；quote 必须通过 shared mapper 的连续文本锚定。
5. **partial answer**：若部分命名实体有验证证据、另一些没有 Top-10 支持，则只展示已验证部分，并列出未覆盖实体。
6. **人审和写作**：自动 grounding 不代替语义审核。人工审核通过的 Claim 才进入 Evidence Matrix 和作者可编辑双语草稿。
7. **交付**：FastAPI/SSE 提供 job 生命周期；Docker 默认 Offline Demo、非 root、只读输入、localhost 端口和显式 Online profile。

## 为什么没有一开始使用 Agent、Dense 或 Vector DB

先建立可审计的最小证据链比先增加编排复杂度更重要。当前 185 passages 的规模不需要 Vector DB。多 Agent、LangGraph 或循环自我反思会放大状态和评估难度，无法替代 citation/quote 的确定性验证。

## 为什么 BM25 超过当前 Dense

在固定 20-query human-reviewed pilot 上，固定 windowing 后 Dense/Hybrid 仍未超过 BM25-ZH-raw 的 Recall@10。当前工程选择了更简单、延迟更低、可解释的 BM25 路径，并通过受控中译英提高中文问题对英文论文的检索覆盖，而不是为了追热点继续调参。

## 如何发现并修复中文 Query 乱码

人工 qrels 审核发现 `query_zh` 在 CSV 中已经变成连续 ASCII `?`，不是 Excel 显示问题。随后沿 JSON、CSV、writer 和控制台链路定位有损编码边界，统一使用 UTF-8 读写和 round-trip 测试。历史中文检索结果被明确标记为无效，而不是悄悄重算或复用。

## LLM 结构化输出失败如何归因

运行 artifact 保留 raw response、usage、latency、manifest、checkpoint 和 validation report。失败被区分为 transport、schema、entity binding、citation membership、quote grounding 或 provider failure；不能把技术失败伪装成正确的 insufficient-evidence 拒答。

## 为什么 citation grounding 不等于语义正确

严格锚定只能证明 quote 位于指定 passage 中，并不保证 Claim 没有扩大范围、误读比较条件或遗漏限定语。Run 002 显示 Baseline 可有语义支持却 grounding 失败，Proposed 也可 grounding 通过却需要人工修订。因此自动验证和人审是正交层。

## Partial Answer 与 Entity Binding

每条 Claim 显式声明 `subject_paper_key` 与 `subject_entity_name`。citation 所属 paper 必须一致，且 claim 不能把其他论文方法归给该实体。若 TPMN 等实体不在当前 Top-10 中，系统显示 partial coverage，而不是借用别的论文内容补全。

## Docker 与安全设计

默认容器是 Offline Demo，绑定 `127.0.0.1`、非 root、只读根文件系统和只读 demo inputs。Online profile 需要显式变量；缺 key 在服务启动前 fail closed。Online jobs 使用独立 named volume，输入语料不写入镜像。

## 最失败的一次实验

`v0.3A` Deep Reading Vertical Slice 在两个在线响应中都产生了目标对象数量，但失败于严格领域 schema 和后续对象摄入边界。离线 normalization 也无法形成有效 preview，因此结论是 `experimental_fail`。这促使项目优先投资 passage-level retrieval、evidence validation 和人审，而不是继续扩展 schema。

## 如果继续开发

先保持现有评估与安全边界，再在新样本上验证 evidence coverage。可能方向包括更受控的中文原生语料扩展和受审阅的检索评估；不应直接重新开启 Prompt 调优、Agent 或无验证的自动综述。

## 诚实边界

- `v0.3A=experimental_fail`。
- Dense/Hybrid 未超过当前 BM25。
- QA availability 有限，answerable grounded answer success 为 `9/17`。
- 检索 pilot 只有 20 条 query。
- 中文原生语料仍是 smoke 级支持。
