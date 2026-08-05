# 证据锚定机制

`litflow` 不把 LLM 输出直接当成可信证据，而是把它当成草稿和选择建议。

核心规则很简单：

```python
evidence_text in chunk_text
```

也就是说，最终进入 structured reading note 的每一条证据文本，都必须能在来源 chunk 中逐字找到。

## 为什么需要这样做

真实 PDF 抽取文本里经常有换行、断词、页眉页脚、表格碎片和格式噪声。LLM 很容易把这些文本整理得更自然，但这样会带来一个问题：生成出来的“证据原文”可能已经不再是 PDF 抽取文本中的逐字原文。

早期测试暴露了两个问题：

- LLM 会规范化或改写 `evidence_text`；
- LLM 在多 chunk 输入时可能声明了看似合理但实际错误的 `chunk_id`。

所以当前版本不再让 LLM 拥有最终证据坐标的决定权。

## Anchored Pipeline

当前证据锚定流程把“模型判断”和“证据归属”分开：

```text
clean chunk
-> LLM 只针对当前 chunk 提出 claim + quote_hint
-> 程序填充 chunk_id 和 page range
-> 程序从 chunk_text 中截取 exact evidence_text
-> LLM 在最终笔记阶段只选择 candidate_id
-> 程序把 candidate_id 映射回 exact evidence_text
-> 执行严格校验
```

LLM 不再自由生成最终的 `chunk_id`、`page_start`、`page_end` 或 `evidence_text`。

## 仍然需要人工确认什么

严格证据锚定只能证明一件事：这段证据确实来自对应 source chunk。

它不能证明：

- claim 对证据的解释一定最准确；
- 生成的中文精读笔记已经可以直接用于论文；
- 这篇文献一定值得引用；
- 这条证据足以支撑你的论文论点。

因此 `litflow` 仍然坚持 preview-first：先生成可审阅 preview，只有用户明确确认后，才允许写入 Obsidian。
