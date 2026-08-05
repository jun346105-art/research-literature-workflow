# 评估与验收指标

`litflow` 评估的是科研文献工作流系统，而不是缺陷检测模型，也不是一次性论文总结器。

本项目不使用 mAP、Precision、Recall 或“总结准确率”作为主要指标，因为它不训练计算机视觉模型，也不声称 LLM 生成的文字天然正确。

当前 MVP 主要评估：

- 工作流是否跑通；
- 证据是否可追溯；
- evidence 是否严格来自原始 chunk；
- Obsidian 写入是否安全；
- 测试是否可重复运行。

## 小批量 E2E 验收

当前验收主题是：

```text
logistics package defect detection RGB-D geometric verification YOLO
```

| 类别 | 指标 | 结果 |
| --- | --- | ---: |
| 文献发现 | candidates_found | 50 |
| 人工筛选 | selected_papers | 8 |
| Zotero | zotero_snapshot_items | 8 |
| PDF | pdf_exists_rate | 8 / 8 |
| 上下文 | reading_context_success | 8 / 8 |
| 上下文 | clean_context_success | 8 / 8 |
| 质量门控 | ready_for_llm_rate | 8 / 8 |
| LLM 精读 | original_structured_notes | 4 |
| 证据管线 | anchored_candidate_banks | 4 |
| 证据管线 | anchored_final_notes | 4 |
| 预览 | anchored_previews_ready | 4 |
| 写入安全 | approved_marker_apply | 1 |
| 测试 | pytest | 101 passed |

## Dogfood Run 001

在小批量 E2E 验收之后，项目又用 2 篇尚未进入 anchored final note 的新论文做了一次 dogfood 验证。

| 指标 | 结果 |
| --- | ---: |
| papers_tested | 2 |
| evidence_candidate_banks_created | 2 / 2 |
| anchored_final_notes_created | 2 / 2 |
| anchored_previews_created | 2 / 2 |
| strict_evidence_failures | 0 |
| manual_polish_required | 1 / 2 |
| approved_marker_apply_after_review | 1 |

Dogfood 记录见 [DOGFOOD_RUN_001.md](DOGFOOD_RUN_001.md)。它故意保持小规模：目标是证明系统能在新的本地论文上继续跑通，而不是把私人输出和全文证据堆进公开仓库。

## 证据校验

最终证据规则是严格的：

```python
evidence_text in chunk_text
```

也就是说，最终写入 structured note 的 `evidence_text` 必须能在来源 chunk 中逐字找到。

在 anchored pipeline 中：

1. 程序一次只把一个 chunk 作为候选证据来源。
2. LLM 只提出 claim 和 quote hint。
3. 程序填充 `chunk_id`、`page_start`、`page_end`。
4. 程序从原始 `chunk_text` 中截取最终 `evidence_text`。
5. 只有当 `evidence_text` 是 `chunk_text` 的逐字子串时，structured note 才能通过。

详细机制见 [证据锚定机制](EVIDENCE_GROUNDING.zh-CN.md)。

## 安全边界指标

| 安全边界 | 结果 |
| --- | ---: |
| 写 Zotero | 0 |
| 修改 Zotero SQLite | 0 |
| 自动下载 PDF | 0 |
| 未确认写入 Obsidian | 0 |
| 无 backup apply | 0 |
| marker 区域外写入 | 0 |

## 这些指标证明了什么

当前 MVP 证明：一批真实文献可以经过下面的流程：

```text
文献发现 -> 人工筛选 -> Zotero snapshot -> PDF context -> clean chunks -> evidence bank -> structured note -> preview -> approved marker apply
```

并且在这个过程中保持证据可追溯、写入可审查、Obsidian 修改可回滚。

## 这些指标不证明什么

当前指标不证明：

- LLM 生成文字完全正确；
- 生成笔记可以不经人工检查直接引用；
- 扫描版 PDF 不需要 OCR 就能处理；
- 当前系统已经是多用户线上生产服务；
- 它可以替代 Zotero、Obsidian 或人工文献综述。

本项目更准确的主张是：`litflow` 提供了一个更安全、可检查、本地优先的 evidence-grounded 文献精读笔记工作流。
