# v0.1+ 小批量 E2E 功能验收记录

## 1. 验收结论

结论：`v0.1+` 小批量 E2E 功能验收通过。

本轮验证了一个真实主题下的 8 篇文献从 discovery、人工筛选、Zotero 读取、Obsidian inbox note、PDF reading context、clean context、quality gate、4 篇 LLM 结构化精读、4 篇 preview、2 篇人工确认 apply 的完整链路。

## 2. 测试主题

```text
logistics package defect detection RGB-D geometric verification YOLO
```

中文理解：

```text
物流包装箱缺陷检测、RGB-D 感知、深度图几何验证、YOLO 候选检测、包装箱破损/变形检测。
```

## 3. 数量汇总

| 项目 | 数量 |
| --- | ---: |
| paper-search-pro 候选 | 50 |
| selected 文献 | 8 |
| Zotero collection 读取 | 8 |
| pdf_exists=true | 8 |
| Obsidian inbox note | 8 |
| reading_context | 8 |
| clean_reading_context | 8 |
| quality gate ready_for_llm | 8 |
| LLM structured reading | 4 |
| evidence validation 通过 | 4 |
| preview | 4 |
| apply | 2 |
| backup | 2 |
| pytest | 84 passed |

Zotero collection：

```text
litflow_e2e_logistics_package_defect_test
```

## 4. 8 篇文献列表

| Zotero key | Citation key | Title |
| --- | --- | --- |
| L4DLHQUZ | he2024tpmntextureprior | TPMN: Texture prior-aware multi-level feature fusion network for corrugated cardboard parcels defect detection |
| Z5HMPJQG | song2023ssdbasedcarton | SSD-based carton packaging quality defect detection system for the logistics supply chain |
| Q55RU9N6 | rogalka2024insituclassification | In-situ classification of highly deformed corrugated board using convolution neural networks |
| JRIUZQ58 | rogalka2024decipheringdoublewalled | Deciphering double-walled corrugated board geometry using image analysis and genetic algorithms |
| 3NF6ZYI5 | yang2020detectingdefectswith | Detecting defects with support vector machine in logistics packaging boxes for edge computing |
| 696N7XZ8 | zhang2024corrugatedcardboarddefect | Corrugated cardboard defect detection based on attention mechanism and lightweight improvements in yolov8 |
| UH62I5UT | matyi2023aninnovativeframework | An innovative framework for quality assurance in logistics packaging |
| 2V3T43BS | prastiwinarti2024efficientpackagingdefect | Efficient packaging defect detection: leveraging pre-trained vision models through transfer learning |

## 5. PDF / Context / Quality Gate 状态

| Zotero key | PDF exists | reading_context | clean_reading_context | Pages | Chunks | Clean chars | Quality status | Warnings |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| L4DLHQUZ | true | success | success | 10 | 16 | 47201 | ready_for_llm | 无 |
| Z5HMPJQG | true | success | success | 7 | 7 | 21655 | ready_for_llm | 无 |
| Q55RU9N6 | true | success | success | 15 | 22 | 66182 | ready_for_llm | references section detected |
| JRIUZQ58 | true | success | success | 19 | 31 | 95213 | ready_for_llm | 无 |
| 3NF6ZYI5 | true | success | success | 9 | 14 | 41172 | ready_for_llm | 无 |
| 696N7XZ8 | true | success | success | 10 | 8 | 25175 | ready_for_llm | references section detected |
| UH62I5UT | true | success | success | 13 | 16 | 48943 | ready_for_llm | references section detected |
| 2V3T43BS | true | success | success | 11 | 15 | 44418 | ready_for_llm | 无 |

## 6. 4 篇 LLM 精读与 Evidence 校验

| Zotero key | Citation key | Structured note | evidence_links | Evidence validation | not_found 情况 |
| --- | --- | --- | ---: | --- | --- |
| L4DLHQUZ | he2024tpmntextureprior | `outputs/e2e_logistics_package_defect_batch/structured_reading_notes/L4DLHQUZ_he2024tpmntextureprior.json` | 5 | passed | 无大量 not_found |
| 696N7XZ8 | zhang2024corrugatedcardboarddefect | `outputs/e2e_logistics_package_defect_batch/structured_reading_notes/696N7XZ8_zhang2024corrugatedcardboarddefect.json` | 4 | passed | `relevance_to_my_research` 为 not_found |
| JRIUZQ58 | rogalka2024decipheringdoublewalled | `outputs/e2e_logistics_package_defect_batch/structured_reading_notes/JRIUZQ58_rogalka2024decipheringdoublewalled.json` | 4 | passed | `relevance_to_my_research` 为 not_found |
| 3NF6ZYI5 | yang2020detectingdefectswith | `outputs/e2e_logistics_package_defect_batch/structured_reading_notes/3NF6ZYI5_yang2020detectingdefectswith.json` | 4 | passed | `relevance_to_my_research` 为 not_found |

Evidence validation 规则保持严格：

- `chunk_id` 必须存在。
- `page_start` / `page_end` 必须匹配对应 chunk。
- `evidence_text` 必须逐字出现在对应 chunk 文本中。
- 不自动改写 `evidence_text`。
- 不静默删除失败 evidence。

## 7. 4 篇 Preview 路径

| Zotero key | Preview path | Target note |
| --- | --- | --- |
| L4DLHQUZ | `outputs/e2e_logistics_package_defect_batch/obsidian_update_previews/L4DLHQUZ_he2024tpmntextureprior_preview.md` | `<ObsidianVault>/00_Inbox/LiteratureReview/@he2024tpmntextureprior.md` |
| 696N7XZ8 | `outputs/e2e_logistics_package_defect_batch/obsidian_update_previews/696N7XZ8_zhang2024corrugatedcardboarddefect_preview.md` | `<ObsidianVault>/00_Inbox/LiteratureReview/@zhang2024corrugatedcardboarddefect.md` |
| JRIUZQ58 | `outputs/e2e_logistics_package_defect_batch/obsidian_update_previews/JRIUZQ58_rogalka2024decipheringdoublewalled_preview.md` | `<ObsidianVault>/00_Inbox/LiteratureReview/@rogalka2024decipheringdoublewalled.md` |
| 3NF6ZYI5 | `outputs/e2e_logistics_package_defect_batch/obsidian_update_previews/3NF6ZYI5_yang2020detectingdefectswith_preview.md` | `<ObsidianVault>/00_Inbox/LiteratureReview/@yang2020detectingdefectswith.md` |

## 8. 2 篇 Apply 结果

本轮只 apply 2 篇，另外 2 篇未写入。

| Zotero key | Applied target note | Backup path | Apply status |
| --- | --- | --- | --- |
| L4DLHQUZ | `<ObsidianVault>/00_Inbox/LiteratureReview/@he2024tpmntextureprior.md` | `outputs/obsidian_backups/@he2024tpmntextureprior.20260701214215.md` | applied |
| 696N7XZ8 | `<ObsidianVault>/00_Inbox/LiteratureReview/@zhang2024corrugatedcardboarddefect.md` | `outputs/obsidian_backups/@zhang2024corrugatedcardboarddefect.20260701214215.md` | applied |

Apply manifest：

```text
outputs/e2e_logistics_package_defect_batch/obsidian_update_apply_manifest.json
```

Apply 后校验：

- 2 篇 target note 中 marker 区域数量正确：`START=1`，`END=1`。
- YAML frontmatter 保持不变。
- marker 外正文内容保持不变。
- preview 的 Proposed Reading Sections 已进入 marker 区域。
- `evidence_text` 未改写。
- 未重命名 Markdown 文件。
- 未移动到 `10_Literature`。
- 未 apply 的 `JRIUZQ58` 和 `3NF6ZYI5` marker count 仍为 0。

## 9. 测试结果

最终测试命令：

```powershell
python -m pytest -q -p no:cacheprovider --basetemp ".\pytest_tmp_e2e_apply2"
```

结果：

```text
84 passed in 1.39s
```

## 10. 当前限制

- 本轮只 apply 2 篇，不代表所有 8 篇都已写入 Obsidian 精读正文。
- 未进入文献综述生成。
- 未做标签治理或 MECE 标签库维护。
- 未自动下载 PDF。
- 未写入 Zotero。
- 未修改 Zotero SQLite。
- 未自动移动笔记到 `10_Literature`。
- LLM 输出仍必须保留 evidence validation 与人工确认环节。
