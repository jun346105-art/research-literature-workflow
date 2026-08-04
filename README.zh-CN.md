# Research Literature Workflow

中文 | [English](README.md)

一个本地优先的科研文献工作流工具，用于连接 `paper-search-pro`、Zotero、Obsidian 与兼容 OpenAI API 的大模型，实现可审计、可人工确认、证据可回溯的结构化文献精读。

## 项目定位

`litflow` 不是普通的 AI 论文总结器。它更像一个本地文献工作流编排层：

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

核心设计原则：LLM 输出不能直接进入知识库。证据片段必须回到 PDF chunk 中锚定，并通过严格校验后，才允许进入 Obsidian 预览；正式写入还需要人工确认。

## 核心能力

- 读取 `paper-search-pro` 输出文件，不修改上游 skill 源码。
- 生成候选论文池和人工筛选模板。
- 导出 BibTeX / RIS，供用户手动导入 Zotero。
- 只读 Zotero collection，不写 Zotero，不碰 Zotero SQLite。
- 基于 Zotero snapshot 生成 Obsidian inbox 文献笔记模板。
- 从本地 PDF 抽取 page-level 文本。
- 清洗文本、识别弱章节、chunk 切分、quality gate。
- 构建 chunk-constrained evidence candidate bank。
- 基于 anchored evidence bank 生成结构化精读笔记。
- 生成 Obsidian update preview。
- 人工确认后，将 preview 写入 Obsidian marker 区域，并自动 backup。

## 安全边界

- Zotero 自动化仅只读。
- PDF 只读本地附件，不自动下载。
- Obsidian 写入必须先生成 preview，并显式传入 `--approved`。
- apply 只替换下面 marker 区域：

```markdown
<!-- LITFLOW_STRUCTURED_READING_START -->
...
<!-- LITFLOW_STRUCTURED_READING_END -->
```

- YAML frontmatter 和 marker 外用户手写内容保持不变。
- `.env`、PDF、Zotero 数据库、Obsidian 私人库、`outputs/` 生成结果都被 `.gitignore` 排除。

## Anchored Evidence Pipeline

当前最可靠的 LLM 精读路径是 anchored pipeline：

```powershell
$env:PYTHONPATH = "src"

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

人工检查 preview 后，才允许执行：

```powershell
python -m litflow.cli apply-obsidian-update `
  --preview ".\outputs\obsidian_update_previews\PAPER_preview.md" `
  --target "<ObsidianVault>\00_Inbox\LiteratureReview\@paper2026sample.md" `
  --manifest ".\outputs\obsidian_update_apply_manifest.json" `
  --approved
```

## 为什么要做 evidence anchoring

早期直接让 LLM 输出 `evidence_text` 和 `chunk_id`，真实测试中出现过两个问题：

- LLM 会把 PDF 原文整理得更“干净”，导致证据文本不再是原文逐字片段。
- LLM 在多 chunk 输入下可能声明错误的 `chunk_id`。

当前方案改为：

```text
一次只给 LLM 一个 chunk
-> LLM 只输出 claim + quote_hint
-> 程序填充 chunk_id / page_start / page_end
-> 程序从 chunk_text 中截取 exact evidence_text
-> 最终校验 evidence_text in chunk_text
-> LLM 后续只选择 candidate_id
```

也就是说，最终 `evidence_text`、`chunk_id` 和页码由程序控制，不由 LLM 自由生成。

## 文档

- 完整命令链：[docs/END_TO_END_WORKFLOW.md](docs/END_TO_END_WORKFLOW.md)
- 架构说明：[ARCHITECTURE.md](ARCHITECTURE.md)
- 项目状态：[PROJECT_STATUS.md](PROJECT_STATUS.md)
- paper-search-pro 本地 skill 工作流：[docs/PAPER_SEARCH_PRO_SKILL_WORKFLOW.md](docs/PAPER_SEARCH_PRO_SKILL_WORKFLOW.md)
- 脱敏示例数据：[examples/README.md](examples/README.md)

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
- 已验证 8 篇文献的小批量本地工作流。
- 已验证 4 篇文献的 LLM 精读链路。
- 当前测试：97 passed。

## 当前限制

- 当前是本地 CLI workflow，不是线上 SaaS。
- 暂不支持扫描版 PDF OCR。
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
