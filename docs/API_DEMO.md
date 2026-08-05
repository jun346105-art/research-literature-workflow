# API Demo With Sample Data / 使用 Sample Data 调用 API

This demo shows how to call the minimal FastAPI wrapper with sanitized sample data.

It does not require Zotero, real PDFs, a real Obsidian vault, or an LLM API key because it only calls the preview endpoint.

这个示例用于展示：访问者如何在本地启动 FastAPI 服务，并用仓库内置的脱敏 sample data 调用 API 生成 Obsidian preview。

它不需要 Zotero、真实 PDF、真实 Obsidian Vault 或 LLM API key，因为这里演示的是安全的 preview endpoint。

## 1. Start The API / 启动 API

```powershell
cd "<repo>"
$env:PYTHONPATH = "src"
uvicorn litflow_api.app:app --reload
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

You should see these endpoints / 页面中应看到这些接口：

- `GET /health`
- `POST /evidence-candidate-bank`
- `POST /structured-note-from-bank`
- `POST /preview-obsidian-update`

## 2. Check Health / 检查服务

PowerShell:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"
```

Expected response:

```json
{
  "status": "ok"
}
```

## 3. Generate A Preview From Sample Data / 使用示例数据生成 preview

PowerShell:

```powershell
$body = @{
  structured_note = "examples/structured_reading_notes/SAMPLE001_structured_reading_note.json"
  vault = "examples/obsidian_vault"
  inbox = "00_Inbox/LiteratureReview"
  out = "examples_output_api/SAMPLE001_preview.md"
  manifest = "examples_output_api/SAMPLE001_preview_manifest.json"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/preview-obsidian-update" `
  -ContentType "application/json" `
  -Body $body
```

Expected response:

```json
{
  "status": "preview_created",
  "target_note_path": "examples\\obsidian_vault\\00_Inbox\\LiteratureReview\\@chen2026samplepackage.md",
  "preview_path": "examples_output_api\\SAMPLE001_preview.md",
  "manifest_path": "examples_output_api/SAMPLE001_preview_manifest.json",
  "warnings": []
}
```

Generated files:

```text
examples_output_api/SAMPLE001_preview.md
examples_output_api/SAMPLE001_preview_manifest.json
```

Reference output:

```text
examples/expected_outputs/SAMPLE001_preview.md
```

## 4. Swagger UI Steps / Swagger UI 操作说明

If using the browser / 如果使用浏览器页面：

1. Open `http://127.0.0.1:8000/docs`.
2. Expand `POST /preview-obsidian-update`.
3. Click `Try it out`.
4. Paste this JSON:

```json
{
  "structured_note": "examples/structured_reading_notes/SAMPLE001_structured_reading_note.json",
  "vault": "examples/obsidian_vault",
  "inbox": "00_Inbox/LiteratureReview",
  "out": "examples_output_api/SAMPLE001_preview.md",
  "manifest": "examples_output_api/SAMPLE001_preview_manifest.json"
}
```

5. Click `Execute`.
6. Open `examples_output_api/SAMPLE001_preview.md`.

## Why The API Demo Does Not Apply To Obsidian / 为什么 demo 不直接写入 Obsidian

The first API wrapper intentionally does not expose an apply endpoint.

Applying a preview writes to a real Obsidian note. That operation should stay behind explicit approval, dry-run checks, backup creation, and human review.

The API demo is therefore limited to safe generation and preview.

也就是说，这个 API demo 只证明后端可以接收 sample data、生成 preview 和 manifest；真正写入 Obsidian 仍然保留在 CLI 的人工确认流程中。
