# Research Literature Workflow

中文 | [English](README.md)

把零散论文变成可追溯、可复用的 Obsidian 精读笔记。

`litflow` 是一个本地优先的科研文献工作流工具，面向使用 Zotero、Obsidian、PDF 和兼容 OpenAI API 大模型的本科生、研究生和科研初学者。它不是一次性的 AI 论文总结器，而是帮助你把文献检索、筛选、精读、证据追溯和 Obsidian 笔记沉淀串成一个可持续复用的流程。

## 为什么需要这个项目

普通 AI 论文总结器很快，但在论文写作和长期文献管理中有几个问题：

- 文献元数据容易和 Zotero 脱节；
- AI 给出的证据很难追溯回 PDF 原文；
- LLM 可能会把 PDF 原文“整理干净”，导致引用片段不再是逐字原文；
- AI 生成内容如果直接写入 Obsidian，容易污染长期知识库；
- 一次性总结很难沉淀成后续开题、综述和论文写作可复用的素材。

`litflow` 的设计是让原有工具继续各司其职：

- Zotero 仍然是文献元数据、PDF、批注和 citation key 的唯一可信来源；
- Obsidian 仍然是本地 Markdown 知识库；
- LLM 只做结构化精读辅助，不直接决定最终证据文本；
- 最终 `evidence_text` 必须是 source chunk 的逐字子串；
- 写入 Obsidian 之前必须先 preview，人工确认后才允许 apply，并且 apply 前会自动 backup。

## 工作流

```text
paper-search-pro 检索结果
-> candidate_pool.json
-> 人工筛选
-> BibTeX / RIS 导出
-> 用户手动导入 Zotero
-> 只读 Zotero snapshot
-> Obsidian inbox 笔记
-> PDF reading context
-> clean chunks + quality gate
-> evidence candidate bank
-> structured reading note
-> Obsidian preview
-> approved marker-region apply
```

## 快速试用 Sample

sample 数据是脱敏 toy text，不需要 Zotero、真实 PDF、真实 Obsidian vault 或 LLM API key。

```powershell
$env:PYTHONPATH = "src"

python -m litflow.cli preview-obsidian-update `
  --structured-note ".\examples\structured_reading_notes\SAMPLE001_structured_reading_note.json" `
  --vault ".\examples\obsidian_vault" `
  --inbox "00_Inbox/LiteratureReview" `
  --out ".\examples_output\SAMPLE001_preview.md" `
  --manifest ".\examples_output\SAMPLE001_preview_manifest.json"
```

参考输出：

[examples/expected_outputs/SAMPLE001_preview.md](examples/expected_outputs/SAMPLE001_preview.md)

更多步骤见：[docs/QUICKSTART.zh-CN.md](docs/QUICKSTART.zh-CN.md)

## 和普通 AI 总结器有什么不同

### 不是 summary-only，而是 evidence-grounded

普通总结器通常是：

```text
PDF -> AI 总结 -> 结束
```

`litflow` 更关注：

```text
claim + source chunk + page range + exact evidence_text + reviewable note
```

最终证据校验规则是：

```python
evidence_text in chunk_text
```

也就是说，最终 evidence 必须能在原始 chunk 中逐字找到。

### 不让 LLM 直接生成最终 evidence_text

真实测试中，LLM 容易出现两个问题：

- 把 PDF 原文中的换行、断词、空格整理成更自然的文本；
- 在多 chunk 输入下声明错误的 `chunk_id`。

当前 anchored pipeline 改为：

```text
一次只给 LLM 一个 chunk
-> LLM 只输出 claim + quote_hint
-> 程序填充 chunk_id / page_start / page_end
-> 程序从 chunk_text 中截取 exact evidence_text
-> 严格校验 evidence_text in chunk_text
-> LLM 后续只选择 candidate_id
```

最终的 `evidence_text`、`chunk_id` 和页码由程序控制，而不是由 LLM 自由生成。

### 贴合本科生 / 研究生真实文献工作流

很多学生已经在使用 Zotero 和 Obsidian。`litflow` 不要求你迁移到新平台，而是在现有工具链上增强：

- Zotero 管理文献元数据和 PDF；
- Obsidian 沉淀精读笔记和双链知识；
- litflow 负责把检索、筛选、PDF chunk、LLM 精读、preview/apply 串起来。

它的目标不是替你直接写完整综述，而是先帮你积累可追溯的精读素材，支撑后续开题、相关工作、方法对比和论文写作。

## 核心命令

Anchored evidence path：

```powershell
python -m litflow.cli build-evidence-candidate-bank `
  --clean-context ".\outputs\clean_reading_context\PAPER.json" `
  --out ".\outputs\evidence_candidate_banks\PAPER_evidence_candidates.json" `
  --report ".\outputs\evidence_candidate_banks\PAPER_evidence_candidates_report.json"

python -m litflow.cli generate-note-from-evidence-bank `
  --candidate-bank ".\outputs\evidence_candidate_banks\PAPER_evidence_candidates.json" `
  --clean-context ".\outputs\clean_reading_context\PAPER.json" `
  --out ".\outputs\structured_reading_notes\PAPER_anchored_final.json" `
  --zotero-key "PAPER" `
  --citation-key "paper2026sample" `
  --title "Sample Paper Title"

python -m litflow.cli preview-obsidian-update `
  --structured-note ".\outputs\structured_reading_notes\PAPER_anchored_final.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview" `
  --out ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --manifest ".\outputs\obsidian_update_preview_manifest.json"
```

人工检查 preview 后，才执行：

```powershell
python -m litflow.cli apply-obsidian-update `
  --preview ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --target "<ObsidianVault>\00_Inbox\LiteratureReview\@paper2026sample.md" `
  --manifest ".\outputs\obsidian_update_apply_manifest.json" `
  --approved
```

## 文档

- [快速开始](docs/QUICKSTART.zh-CN.md)
- [核心概念](docs/CONCEPTS.zh-CN.md)
- [常见问题排查](docs/TROUBLESHOOTING.md)
- [最小 FastAPI wrapper](docs/API.md)
- [架构说明](ARCHITECTURE.md)
- [完整命令链](docs/END_TO_END_WORKFLOW.md)
- [项目状态](PROJECT_STATUS.md)
- [paper-search-pro 本地 skill 工作流](docs/PAPER_SEARCH_PRO_SKILL_WORKFLOW.md)
- [脱敏示例数据](examples/README.md)

## 环境变量

复制 `.env.example`，只在本地填写真实值。不要提交真实 key。

```text
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
ZOTERO_LIBRARY_ID=
ZOTERO_API_KEY=
OBSIDIAN_VAULT_PATH=
PAPER_SEARCH_PRO_RESULT_DIR=
```

## 当前状态

- `v0.1-small-batch-e2e`：已完成并打 tag。
- `v0.1.1-anchored-evidence-pipeline`：已加入 anchored evidence pipeline 和脱敏 examples。
- 已用本地 Zotero、PDF、Obsidian 和兼容 OpenAI API 的 LLM 验证小批量工作流。
- 当前测试：97 passed。

## 当前限制

- 当前是本地 CLI workflow，不是线上 SaaS。
- 暂不支持扫描版 PDF OCR。
- 暂不自动下载 PDF。
- 暂不自动生成完整文献综述。
- 暂不自动治理标签库。
- 不写 Zotero。
- 不自动移动 Obsidian 笔记到正式库。
- section detection 是轻量规则，不保证完美。
- LLM 输出必须经过 schema validation、evidence validation 和人工确认。

## 开发检查

```powershell
$env:PYTHONPATH='src;C:\Users\GigaByte\Documents\Codex\2026-07-01\obsidian\work\pydeps'
python -m pytest -q -p no:cacheprovider --basetemp ".\pytest_tmp_dev"
```
