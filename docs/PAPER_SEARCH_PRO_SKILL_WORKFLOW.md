# Paper Search Pro Skill Workflow

`paper-search-pro` is an external local Codex skill and the discovery layer for this project.

`litflow` does not implement literature search algorithms, does not copy `paper-search-pro` into this project, and does not modify the `paper-search-pro` skill source code. The user first runs the local skill to search papers, then `litflow` reads the exported files.

Suggested output directory for each search:

```text
<PAPER_SEARCH_PRO_RESULT_DIR>/2026-07-01-logistics-defect-detection/
```

Recommended files in that directory:

```text
papers.json
papers.csv
papers.bib
papers.ris
report.md
report.html
```

Inspect the result directory:

```powershell
$env:PYTHONPATH = "src"

python -m litflow.cli inspect-psp-results `
  --input "<PAPER_SEARCH_PRO_RESULT_DIR>/2026-07-01-logistics-defect-detection"
```

Build the candidate pool:

```powershell
python -m litflow.cli build-candidate-pool `
  --input "<PAPER_SEARCH_PRO_RESULT_DIR>/2026-07-01-logistics-defect-detection" `
  --output "./outputs/candidate_pool.json"
```

Create the manual selection file:

```powershell
python -m litflow.cli select-candidates `
  --candidates "./outputs/candidate_pool.json" `
  --out "./outputs/selected_candidates.json"
```

Edit `selected_candidates.json` manually and set papers to import:

```json
"selected": true
```

Export a Zotero import file:

```powershell
python -m litflow.cli export-zotero-import `
  --selected "./outputs/selected_candidates.json" `
  --format bib `
  --out "./outputs/selected.bib"
```

The user then manually imports `selected.bib` or `selected.ris` into Zotero. This phase does not call Zotero APIs, download PDFs, generate Obsidian notes, run LLM reading, or generate literature reviews.
