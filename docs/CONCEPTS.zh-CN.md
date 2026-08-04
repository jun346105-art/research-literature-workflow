# 核心概念

## Reading Context

每篇文献对应一个 JSON 文件，由 Zotero 元数据、本地 PDF 文本、Zotero note / annotation 组成。

它保留 page-level 文本和 warning，位于 LLM 步骤之前。

## Clean Context

Reading context 的轻量清洗版本。清洗策略刻意保守：

- 统一换行；
- 修复简单英文断词换行；
- 折叠过多空行；
- 尽量保持接近 PDF 抽取文本。

## Chunk

chunk 是 clean paper text 的字符窗口切片。

默认参数：

```text
chunk_size_chars = 3500
chunk_overlap_chars = 400
```

每个 chunk 保存：

- `chunk_id`
- `page_start`
- `page_end`
- `section_guess`
- `source_page_numbers`
- `text`

## Quality Gate

quality gate 用来判断 clean context 是否适合进入 LLM 精读。

它会标记：

- PDF 抽取文本为空；
- chunk 缺失；
- 文本过短；
- 仍然是 `max_pages` smoke test 输出；
- 所有 section 都是 unknown；
- references 占比过高；
- annotation 对齐异常。

## Evidence Candidate Bank

evidence candidate bank 来自 chunk-constrained extraction。

程序一次只给 LLM 一个 chunk。LLM 只返回：

```json
{
  "claim": "",
  "quote_hint": "",
  "evidence_type": "method"
}
```

程序负责填充：

- `chunk_id`
- `page_start`
- `page_end`

然后程序在当前 chunk 内锚定 `quote_hint`，截取逐字原文片段作为最终 `evidence_text`。

## Strict Evidence Validation

最终证据必须满足：

```python
evidence_text in chunk_text
```

validator 还会检查：

- 引用的 `chunk_id` 是否存在；
- `page_start` / `page_end` 是否和 chunk 匹配；
- evidence text 是否实际上属于其他 chunk。

## Structured Reading Note

结构化文献精读 JSON，包括：

- 一句话总结；
- 研究背景；
- research gap；
- 核心贡献；
- 方法；
- 实验；
- 局限性；
- 与用户研究的关系；
- evidence links。

## Preview / Apply

Preview 会生成供人工检查的 Markdown。

Apply 只写入：

```markdown
<!-- LITFLOW_STRUCTURED_READING_START -->
...
<!-- LITFLOW_STRUCTURED_READING_END -->
```

Apply 必须显式传入 `--approved`，并且写入前会创建 backup。
