# DOGFOOD_RUN_001

## 目的

本次 dogfood 用 2 篇尚未进入 anchored final 的真实文献，验证 `litflow` 是否能从已有 Zotero snapshot / clean context 继续跑到 anchored preview。

本次只生成 preview，不 apply，不写 Obsidian，不修改 Zotero。

## 主题

```text
logistics package defect detection RGB-D geometric verification YOLO
```

## 输入

来自上一轮小批量 E2E 的本地输出：

```text
outputs/e2e_logistics_package_defect_batch/clean_reading_context/
```

选取文献：

| zotero_key | citation_key | title | 选择原因 |
| --- | --- | --- | --- |
| Z5HMPJQG | song2023ssdbasedcarton | SSD-based carton packaging quality defect detection system for the logistics supply chain | 物流供应链纸箱包装缺陷检测，应用场景强 |
| 2V3T43BS | prastiwinarti2024efficientpackagingdefect | Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning | 预训练视觉模型和迁移学习，适合作为方法对比素材 |

## LLM 配置

本次使用 OpenAI-compatible API：

```text
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

API key 通过本地环境变量提供，未写入仓库。

## 执行流程

每篇文献执行：

```text
clean context
-> build-evidence-candidate-bank
-> generate-note-from-evidence-bank
-> preview-obsidian-update
```

关键约束：

- LLM 不直接生成最终 `evidence_text`；
- LLM 不自由选择最终 `chunk_id` / page range；
- 程序从来源 `chunk_text` 截取最终 `evidence_text`；
- 最终严格校验 `evidence_text in chunk_text`；
- preview 生成后停止，不 apply。

## 结果

| zotero_key | chunks | anchored candidates | failed candidates | evidence_links | strict evidence failures | preview status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Z5HMPJQG | 7 | 5 | 7 | 5 | 0 | preview_created |
| 2V3T43BS | 15 | 17 | 7 | 12 | 0 | preview_created |

## 输出文件

```text
outputs/dogfood_run_001/evidence_candidate_banks/Z5HMPJQG_evidence_candidates.json
outputs/dogfood_run_001/evidence_candidate_banks/Z5HMPJQG_evidence_candidates_report.json
outputs/dogfood_run_001/structured_reading_notes/Z5HMPJQG_song2023ssdbasedcarton_dogfood_anchored_final.json
outputs/dogfood_run_001/obsidian_update_previews/Z5HMPJQG_song2023ssdbasedcarton_dogfood_preview.md
outputs/dogfood_run_001/obsidian_update_previews/Z5HMPJQG_song2023ssdbasedcarton_dogfood_preview_manifest.json

outputs/dogfood_run_001/evidence_candidate_banks/2V3T43BS_evidence_candidates.json
outputs/dogfood_run_001/evidence_candidate_banks/2V3T43BS_evidence_candidates_report.json
outputs/dogfood_run_001/structured_reading_notes/2V3T43BS_prastiwinarti2024efficientpackagingdefect_dogfood_anchored_final.json
outputs/dogfood_run_001/obsidian_update_previews/2V3T43BS_prastiwinarti2024efficientpackagingdefect_dogfood_preview.md
outputs/dogfood_run_001/obsidian_update_previews/2V3T43BS_prastiwinarti2024efficientpackagingdefect_dogfood_preview_manifest.json
```

这些输出位于 `outputs/`，不应提交到 git。

## 判断

本次 dogfood 说明：

- 对真实 clean context，anchored pipeline 可以继续生成 evidence candidate bank；
- evidence-bank grounded note generation 可以生成 structured note；
- preview 可以正确匹配 Obsidian inbox 中已有目标 note；
- 两篇最终 `evidence_links` 均通过严格逐字校验；
- `relevance_to_my_research` 均不是 `not_found`。

## 人工审阅结论

本次 dogfood 的目标是评测系统是否真实可用，而不是把 preview 直接修成最终入库稿。

### 2V3T43BS 审阅结果

`2V3T43BS` 的技术链路通过：

- evidence candidate bank 成功生成；
- anchored structured note 成功生成；
- Obsidian preview 成功生成；
- 12 条 `evidence_links` 全部通过严格逐字校验；
- `relevance_to_my_research` 不是 `not_found`；
- 没有 apply，没有写 Obsidian，没有修改 Zotero。

内容质量判断：

- preview 已经可以作为论文写作素材使用；
- 但还不是无需人工确认的最终 Obsidian 入库稿；
- 主要问题不是证据错误，而是若干中文表述需要更保守；
- 例如“100% 准确率”应限定为“在该文实验设置下报告达到”；
- 与 YOLO / hole / wet / scratch 的关系应保持为应用启发，不能写成原文直接验证。

### 人工成本判断

预计从当前 preview 修到可入库状态需要 5-10 分钟。

这说明当前系统有效：它把最耗时的结构化阅读、证据提取、证据定位和 preview 生成完成了，但仍保留 human-in-the-loop 来处理最终措辞和论文写作判断。

### 产品结论

DOGFOOD_RUN_001 的结论不是“自动生成完美笔记”，而是：

```text
litflow 可以在真实文献上生成可审阅、可追溯、证据严格校验通过的精读 preview。
```

当前项目最强的能力是证据可信链和安全写入边界；最终中文表达质量仍需要人工审阅或后处理。

## 风险

- `Z5HMPJQG` 只有 5 条有效 evidence links，刚好达到最低可用线，人工检查时应重点看 claim 是否足够支撑笔记内容。
- `2V3T43BS` 的 evidence 数量更充足，更适合作为下一步人工审阅样例。
- 本次没有 apply，因此没有验证 marker 替换、backup 和 Obsidian 正文保持不变。

## 结论

DOGFOOD_RUN_001 通过。

当前项目不是空壳：它可以在真实文献 clean context 上生成可审阅的 anchored preview，并保持最终 evidence text 的严格可追溯性。

下一步建议人工检查两份 preview。若内容可接受，再选择 1 篇执行 dry-run + approved apply。
