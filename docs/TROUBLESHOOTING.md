# Troubleshooting

## Missing LLM Environment Variables

Error:

```text
Missing LLM environment variables: LLM_BASE_URL
```

Fix:

```powershell
$env:LLM_BASE_URL="https://api.example.com"
$env:LLM_API_KEY="<your-key>"
$env:LLM_MODEL="<model>"
```

Do not commit real keys.

## JSON Parse Failed

The LLM returned invalid JSON or wrapped JSON in extra text.

Current behavior:

- JSON mode is requested when using the OpenAI-compatible client.
- Markdown JSON fences are stripped when possible.
- One retry is allowed.
- If it still fails, a `.error.json` file is written.

## Schema Validation Failed

The LLM returned JSON, but fields do not match `StructuredReadingNote`.

Common example:

```text
expected string, got list
```

The evidence-bank note path normalizes list-like text fields into Markdown bullet text. Other schema errors are preserved in `.error.json`.

## PDF Extraction Is Empty

Likely causes:

- scanned PDF;
- image-only PDF;
- encrypted PDF;
- unsupported layout.

Current behavior:

- empty pages are recorded as warnings;
- OCR is not supported;
- failed extraction prevents the paper from being marked ready.

## Evidence Text Not Found

Error type:

```text
evidence_text_not_found
```

Meaning: final `evidence_text` is not an exact substring of any allowed chunk.

Fix: rerun anchored evidence extraction or inspect the candidate bank. Do not relax strict validation unless you also change the trust model.

## Wrong Chunk ID

Error type:

```text
wrong_chunk_id
```

Meaning: the text exists, but not in the declared chunk.

The anchored pipeline avoids this by giving the LLM only one chunk at a time and letting the program fill `chunk_id`.

## Page Range Mismatch

Error type:

```text
page_range_mismatch
```

Meaning: `page_start` / `page_end` do not match the cited chunk.

Fix: regenerate the note from the clean context or candidate bank. Do not edit page ranges manually unless you know the chunk metadata changed.

## Target Obsidian Note Missing

Preview generation scans Obsidian inbox notes by `zotero_key` frontmatter.

Fix:

```powershell
python -m litflow.cli make-obsidian-notes `
  --items ".\outputs\zotero_collection.json" `
  --vault "<ObsidianVault>" `
  --inbox "00_Inbox/LiteratureReview"
```

## Apply Refuses To Run

Apply requires:

```text
--approved
```

Use dry run first:

```powershell
python -m litflow.cli apply-obsidian-update `
  --preview "<preview.md>" `
  --target "<target.md>" `
  --manifest "<manifest.json>" `
  --dry-run
```
