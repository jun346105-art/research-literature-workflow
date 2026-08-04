# 快速开始

本指南使用脱敏 sample 数据。不需要 Zotero、真实 PDF、真实 Obsidian vault，也不需要 LLM API key。

## 1. 运行 Sample Preview

```powershell
cd "<repo>"
$env:PYTHONPATH = "src"

python -m litflow.cli preview-obsidian-update `
  --structured-note ".\examples\structured_reading_notes\SAMPLE001_structured_reading_note.json" `
  --vault ".\examples\obsidian_vault" `
  --inbox "00_Inbox/LiteratureReview" `
  --out ".\examples_output\SAMPLE001_preview.md" `
  --manifest ".\examples_output\SAMPLE001_preview_manifest.json"
```

预期输出：

```text
examples_output/SAMPLE001_preview.md
examples_output/SAMPLE001_preview_manifest.json
```

参考输出：

```text
examples/expected_outputs/SAMPLE001_preview.md
```

## 2. 检查 Evidence Contract

打开：

```text
examples/clean_context/SAMPLE001.json
examples/structured_reading_notes/SAMPLE001_structured_reading_note.json
```

structured note 中的每条 `evidence_text` 都是对应 chunk 的逐字子串。

## 3. 使用你自己的 Zotero Snapshot

先把筛选后的文献手动导入 Zotero，然后读取 collection：

```powershell
python -m litflow.cli read-zotero-collection `
  --collection "Your Collection" `
  --output ".\outputs\zotero_collection.json"
```

再生成 Obsidian inbox 笔记模板：

```powershell
python -m litflow.cli make-obsidian-notes `
  --items ".\outputs\zotero_collection.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview"
```

## 4. 构建 Reading Context

```powershell
python -m litflow.cli build-reading-context `
  --items ".\outputs\zotero_collection.json" `
  --out-dir ".\outputs\reading_context" `
  --manifest ".\outputs\reading_context_manifest.json"

python -m litflow.cli clean-reading-context `
  --context-dir ".\outputs\reading_context" `
  --manifest ".\outputs\reading_context_manifest.json" `
  --out-dir ".\outputs\clean_reading_context" `
  --out-manifest ".\outputs\clean_reading_context_manifest.json"

python -m litflow.cli audit-clean-context `
  --clean-dir ".\outputs\clean_reading_context" `
  --manifest ".\outputs\clean_reading_context_manifest.json" `
  --out ".\outputs\clean_context_quality_report.json"
```

## 5. 生成 Anchored Note

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
```

## 6. 先 Preview，再 Apply

```powershell
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
