# 面试讲解材料

这份文档用于面试前自查，不是产品文档。目标是让你能讲清楚 `litflow` 的问题定义、系统边界、关键技术点和工程取舍。

## 一句话介绍

`litflow` 是一个本地优先的科研文献工作流工具，把 paper-search-pro、Zotero、PDF、Obsidian 和兼容 OpenAI API 的 LLM 串起来，生成可审阅、可追溯、证据严格校验的文献精读笔记。

它不是普通 AI 论文总结器，核心价值是：

- 文献元数据以 Zotero 为唯一来源；
- PDF 文本被拆成可追溯 chunk；
- LLM 不直接拥有最终证据文本；
- 程序负责 evidence anchoring；
- Obsidian 写入必须 preview、dry-run、backup、approved。

## 项目解决的问题

普通学生做文献管理时，常见问题是：

- 文献检索、Zotero、PDF、Obsidian 笔记彼此割裂；
- LLM 总结看起来流畅，但证据回不到 PDF 原文；
- AI 可能把 PDF 原文的换行、断词、页眉页脚整理掉，导致 quote 不再是逐字原文；
- 自动写入 Obsidian 容易污染长期知识库；
- 一次性总结无法沉淀成后续论文写作可复用素材。

`litflow` 的目标不是替代人工综述，而是把“文献发现 -> 精读素材 -> 可审阅笔记”变成可重复流程。

## 当前做到什么程度

当前公开版本已经完成：

- paper-search-pro 输出读取和 candidate pool 标准化；
- 人工筛选 selected candidates；
- BibTeX / RIS 导出，用户手动导入 Zotero；
- Zotero collection 只读读取；
- Obsidian inbox 空笔记生成；
- 本地 PDF 文本抽取；
- clean reading context 和 quality gate；
- evidence candidate bank；
- evidence-bank grounded structured note；
- Obsidian preview；
- dry-run + approved marker-region apply；
- FastAPI 最小 wrapper；
- sample data 和公开评估文档。

当前不是完整产品：

- 没有自动下载 PDF；
- 没有 OCR；
- 没有自动生成综述；
- 没有批量自动 apply；
- 没有自动标签治理；
- 没有托管多用户 SaaS。

## 技术栈

- Python：核心 CLI、数据模型、PDF 抽取、Zotero/Obsidian 适配；
- Pydantic：结构化模型和 schema validation；
- pypdf：文本型 PDF 抽取；
- FastAPI：最小 API 展示层；
- pytest：单元测试和回归测试；
- Zotero Local API：只读读取 collection、metadata、attachment；
- Obsidian Markdown：笔记输出和 marker 区域更新；
- OpenAI-compatible API：LLM structured reading；
- Git / GitHub：版本管理、开源展示、tag。

## 关键架构边界

### paper-search-pro

定位：discovery layer。

只负责发现候选论文，不替代 Zotero 和 Obsidian。`litflow` 不修改 paper-search-pro 源码，只读取它生成的 `papers.json` / `papers.csv` 等输出。

### Zotero

定位：唯一文献元数据来源。

Zotero 保存 metadata、PDF、annotation、citation key。`litflow` 当前只读 Zotero，不写 Zotero，不改 SQLite。

### Obsidian

定位：本地 Markdown 知识库。

所有自动生成内容先进入 inbox 或 preview。正式写入必须人工确认，只替换 marker 区域，不改 frontmatter，不改 marker 外用户内容。

### LLM

定位：结构化阅读助手。

LLM 可以总结、归纳、选择 evidence candidate，但不能直接决定最终 `evidence_text`、`chunk_id` 和 page range。

## PDF 和 chunk 怎么处理

Phase 3A 用 `pypdf` 读取本地 PDF：

- 只读本地 PDF；
- 不联网；
- 不下载；
- 不 OCR；
- 按页保存文本；
- 记录 page_count、char_count、warnings 和 errors。

Phase 3B 对 reading context 做清理和 chunk：

- 保留页码范围；
- 按固定 chunk size 切分；
- 使用 overlap 保留上下文连续性；
- 记录 section guess；
- 保留 warnings，例如 section 不准、文本过短、扫描版风险。

当前项目默认把 chunk 当成证据追溯单位。每个 chunk 至少包含：

- `chunk_id`
- `page_start`
- `page_end`
- `text`
- `section_guess`

面试时要强调：section detector 是轻量启发式，不把它当强事实，只作为 LLM 阅读提示。

## LLM JSON 不稳定怎么处理

项目里做了几层控制：

- prompt 明确要求 JSON object；
- OpenAI-compatible client 支持 JSON response mode；
- 返回结果必须 JSON parse；
- schema validation 不通过就失败；
- JSON 不合法最多 retry 1 次；
- retry 后仍失败保存 `.error.json`，不静默吞错；
- 不把无效输出写入 Obsidian。

这里的重点不是“prompt 写得好”，而是把 LLM 当作不稳定外部依赖处理。

## evidence 错位问题怎么处理

早期做法是让 LLM 在多 chunk 输入中直接输出：

```text
claim + chunk_id + page_start/page_end + evidence_text
```

真实测试发现两个问题：

- LLM 会把 evidence_text 整理干净，导致不再是 chunk 原文；
- LLM 会选错 chunk_id，即语义接近但坐标错误。

后来的 anchored pipeline 改成：

```text
单 chunk 输入
-> LLM 只输出 claim + quote_hint
-> 程序填充 chunk_id / page_start / page_end
-> 程序从当前 chunk_text 截取 exact evidence_text
-> 生成 evidence candidate bank
-> LLM 在最终笔记阶段只选择 candidate_id
-> 程序映射 candidate_id 得到最终 evidence_links
```

最终校验仍然严格：

```python
evidence_text in chunk_text
```

不允许用 normalized validation 作为最终通过标准。

## 为什么不让 LLM 直接写 Obsidian

因为 Obsidian 是长期知识库，不应该被未审查的模型输出污染。

当前写入流程是：

```text
structured_reading_note.json
-> preview markdown
-> 人工检查
-> dry-run
-> approved apply
-> backup
-> 只替换 marker 区域
```

写入区域：

```text
<!-- LITFLOW_STRUCTURED_READING_START -->
...
<!-- LITFLOW_STRUCTURED_READING_END -->
```

这样可以保证：

- frontmatter 不变；
- marker 外用户手写内容不变；
- 写错可以从 backup 回滚；
- 用户始终拥有最终入库决定权。

## 可以怎么向面试官讲项目亮点

推荐讲法：

> 我做的不是一个简单论文总结器，而是一个本地科研文献工作流。它把 paper-search-pro 的 discovery、Zotero 的文献数据库、PDF 文本抽取、LLM 结构化阅读和 Obsidian 笔记写入串起来。重点是我没有直接信任 LLM 的引用文本，而是设计了 evidence candidate bank 和 programmatic anchoring，保证最终 evidence_text 必须逐字来自 source chunk。写入 Obsidian 也不是自动覆盖，而是 preview、dry-run、backup、approved 的安全流程。

## 面试高频追问

### 这个项目和普通 RAG 有什么区别？

普通 RAG 多数关注“问答时检索相关片段”。`litflow` 关注的是科研工作流里的长期知识沉淀：候选文献、Zotero 元数据、PDF chunk、证据锚定、Obsidian 笔记和人工确认。

### 为什么不用 LLM 直接总结整篇 PDF？

因为整篇总结不可控，证据容易丢失。我的设计把 PDF 转成 chunk，再让 LLM 在受限 chunk 内提出 evidence candidate，最后由程序保证 evidence_text 来自原文。

### 你的 evidence validation 怎么做？

最终条件是 `evidence_text in chunk_text`。如果证据文本不是来源 chunk 的逐字子串，就不能作为最终 evidence link 通过。

### 如果 PDF 是扫描版怎么办？

当前不支持 OCR。quality gate 会把空文本或抽取质量差的 PDF 标记为需要人工检查或失败。这是明确限制，不假装支持。

### 为什么 Zotero 只读？

Zotero 是文献源数据库，写入风险高。当前版本只读取 collection、metadata、PDF path 和 annotation，导入文献仍由用户手动完成。

### FastAPI wrapper 有什么意义？

它不是核心能力，只是把部分 CLI 能力暴露成 API，方便展示后端接口设计、Swagger 文档和 sample 调用。核心工程价值仍然在 workflow 和 evidence grounding。

## 简历写法参考

项目名：Research Literature Workflow / litflow

项目描述：

> 设计并实现一个本地优先的科研文献管理与 LLM 精读工作流，连接 paper-search-pro、Zotero、PDF、Obsidian 和 OpenAI-compatible LLM。系统支持候选文献标准化、Zotero 只读快照、本地 PDF chunk、证据候选库、结构化精读 JSON、Obsidian preview 和安全 apply。针对 LLM 引文不稳定问题，实现 programmatic evidence anchoring，保证最终 evidence_text 可逐字追溯到 source chunk。

技术点：

- Python CLI / FastAPI / Pydantic / pytest；
- Zotero read-only integration；
- PDF text extraction and chunking；
- LLM JSON output parsing and retry；
- evidence grounding and strict validation；
- Obsidian Markdown preview/apply with backup；
- human-in-the-loop workflow design。

## 当前最应该补强的地方

如果继续投入，优先级建议：

1. 固化 2-3 个脱敏 sample workflow，让别人不用真实 Zotero 也能跑。
2. 给 FastAPI wrapper 增加更清楚的 sample endpoint 文档。
3. 做一个小型 demo video 或 GIF，展示 sample 从 JSON 到 preview。
4. 再考虑批量处理和任务队列。

不要急着做自动综述。当前项目最有价值的部分是证据可信链，而不是自动生成更多文字。
