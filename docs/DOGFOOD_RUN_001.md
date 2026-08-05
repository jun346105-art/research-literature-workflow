# DOGFOOD_RUN_001

## 目的

本次 dogfood 用 2 篇新的真实论文验证 `litflow` 是否能在已有 Zotero snapshot / clean context 基础上继续跑通 anchored evidence pipeline。

这不是功能扩展，也不是自动综述测试。目标是检查项目是否真的能在新论文上生成可审阅、可追溯、可安全写入 Obsidian 的精读材料。

## 主题

```text
logistics package defect detection RGB-D geometric verification YOLO
```

## 输入

输入来自上一轮小批量 E2E 的本地输出：

```text
outputs/e2e_logistics_package_defect_batch/clean_reading_context/
```

本次选择 2 篇文献：

| zotero_key | citation_key | title | 选择原因 |
| --- | --- | --- | --- |
| Z5HMPJQG | song2023ssdbasedcarton | SSD-based carton packaging quality defect detection system for the logistics supply chain | 贴近物流供应链中的纸箱包装质量缺陷检测 |
| 2V3T43BS | prastiwinarti2024efficientpackagingdefect | Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 贴近预训练视觉模型、迁移学习和包装缺陷检测 |

## 执行流程

每篇文献执行：

```text
clean context
-> build-evidence-candidate-bank
-> generate-note-from-evidence-bank
-> preview-obsidian-update
```

其中 `2V3T43BS` 在人工检查和 deterministic polish 后继续执行：

```text
dry-run
-> approved marker-region apply
```

关键约束：

- LLM 不直接生成最终 `evidence_text`。
- LLM 不自由决定最终 `chunk_id` / page range。
- 程序从来源 `chunk_text` 截取最终 `evidence_text`。
- 最终严格校验 `evidence_text in chunk_text`。
- 写入 Obsidian 前必须人工检查 preview。
- apply 前必须 dry-run，并创建 backup。

## 结果

| zotero_key | chunks | anchored candidates | failed candidates | evidence_links | strict evidence failures | preview | apply |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Z5HMPJQG | 7 | 5 | 7 | 5 | 0 | preview_created | not_applied |
| 2V3T43BS | 15 | 17 | 7 | 12 | 0 | preview_created | applied_after_review |

## 输出文件

这些输出位于 `outputs/`，不提交到 git：

```text
outputs/dogfood_run_001/evidence_candidate_banks/
outputs/dogfood_run_001/structured_reading_notes/
outputs/dogfood_run_001/obsidian_update_previews/
outputs/dogfood_run_001/obsidian_update_apply_2V3T43BS_manifest.json
```

`2V3T43BS` 写入前已创建 backup：

```text
outputs/obsidian_backups/@prastiwinarti2024efficientpackagingdefect.<timestamp>.md
```

## 人工审阅结论

`2V3T43BS` 的第一版 preview 技术链路通过，但中文表述需要更保守。因此没有直接 apply，而是先做 deterministic polish：

- 删除过强或绝对化表述；
- 保持 `evidence_text`、`chunk_id`、page range 不变；
- 保持 12 条 evidence links；
- 保持 fenced text block 证据格式；
- 不重新调用 LLM。

人工确认 polished preview 后，执行 dry-run 和 approved apply。最终只替换目标 Obsidian note 的 marker 区域，frontmatter 和 marker 外正文保持不变。

## 结论

DOGFOOD_RUN_001 通过。

它证明当前项目不是空壳：`litflow` 可以在新的真实论文上生成 anchored evidence candidate bank、structured reading note 和 Obsidian preview，并能在人工确认后安全写入 marker 区域。

当前项目的价值不在于“自动生成完美笔记”，而在于：

- 把 PDF / Zotero / Obsidian / LLM 串成可重复工作流；
- 用程序控制最终证据文本和来源坐标；
- 用严格校验防止 LLM 改写证据；
- 用 preview / dry-run / backup 保护 Obsidian 知识库。

## 当前限制

- 只验证 2 篇新论文，不代表大规模批量稳定性。
- 其中 1 篇执行 apply，另 1 篇仍停留在 preview。
- 中文精读内容仍需要人工审阅和保守措辞修订。
- 未进入自动综述。
- 未自动下载 PDF。
- 未修改 Zotero。
