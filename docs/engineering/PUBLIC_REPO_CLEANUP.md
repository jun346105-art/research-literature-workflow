# Public repository cleanup — v1.3.1 candidate

Baseline: `4ca1464aada0edb00e3467c3ad45508bafad41bd` (remote main and v1.3.0 peeled commit). This is documentation-only candidate preparation; v1.3.0 and its Release remain unchanged.

## Read-only inventory and disposition

Before editing: **444 tracked files, 18 root files, 8 top-level directories, 73 directories, 137 Markdown files, 12 images**. Counts exclude Git metadata and untracked local artifacts. The inventory checked tracked source/tests, Markdown links and literal references, schemas/manifests, hash dependencies, Release text, licenses, credential/private-path patterns and file sizes.

| Final disposition | Files | Reason |
|---|---:|---|
| Keep | 423 | Source, tests, configuration, schemas, locks, examples, current bilingual documentation/screenshots, and research evidence |
| Move | 20 | Historical presentation and unique reference material retained through Git renames |
| Remove | 1 | Redundant distribution ZIP described below |
| Review | 0 unresolved | Review decisions and exceptions are recorded below |

## Moves

All names below are exact; each group shares its stated source and destination directory.

| Source directory | Files | Destination directory |
|---|---|---|
| repository root | `ARCHITECTURE.md`, `PROJECT_STATUS.md`, `LITFLOW_V1_1_AGENT_ROADMAP.zh-CN.md`, `RELEASE_NOTES_v1.0.0.md`, `RELEASE_NOTES_v1.1.0.md`, `RELEASE_NOTES_v1.2.0.md` | `docs/archive/` |
| `docs/` | `QUICKSTART.md`, `QUICKSTART.zh-CN.md`, `API_DEMO.md`, `RESUME_PROJECT.en.md`, `RESUME_PROJECT.zh-CN.md`, `INTERVIEW_GUIDE.zh-CN.md` | `docs/archive/` |
| `docs/screenshots/` | `litflow-mvp-evidence-matrix.png`, `litflow-mvp-workbench.png`, `litflow-mvp-writing-draft.png` | `docs/archive/screenshots/` |
| `design/references/stitch/litflow_ui_implementation_pack/litflow_ui_implementation_pack/` | `AUDIT.md`, `LITFLOW_UI_DESIGN_SPEC.md`, `M6A_CODEX_UI_IMPLEMENTATION_BRIEF.md`, `reference/STITCH_DESIGN_ORIGINAL.md`, `reference/screen.png` | `docs/archive/stitch/` (retaining `reference/`) |

## Exact deletion decision (recorded before deletion)

- `design/references/stitch/LitFlow_UI_Implementation_Pack.zip`: an unreferenced duplicate packaging of the five expanded Stitch files retained above. Its image is byte-identical; all four Markdown files are identical after normalizing line endings and trailing whitespace. No unique prose, image, runtime input, frozen experiment or hash contract depends on this packaging. The original source ZIP hash in the retained Stitch audit describes a different input archive, not this redundant implementation bundle. No other file is deleted.

## Review decisions and traceability

- Keep all of `docs/deep_research/` byte-for-byte at its existing paths, including R1 results, reviewed records, failure records, Round/Gate/Attempt material, Session logs, Traceability, plans, schemas and manifests. These describe frozen contracts and provenance; their engineering-oriented names are not grounds for deletion.
- Keep `M8_AGENT_EXPERIMENT_CLOSURE.zh-CN.md` at the root because the frozen asset inventory names that path. The remaining root exception protects traceability.
- Keep current API, Demo, architecture, Provider and formal-result material. Add reader-facing evaluation/provider indexes rather than relocating their underlying contracts.
- Keep bilingual concepts, evidence-grounding and evaluation documents: language alternatives serve readers and are not redundant copies.
- Archive the old CLI Quickstarts and API Demo because their structured-note sample is absent from the public tree; preserve the commands as historical documentation. The archive index explains that precondition. Do not fabricate the missing sample or alter the product.
- Archive previously published resume/interview text without rewriting it or starting resume work. It contains project narratives, not personal contact details.
- Keep existing generated schemas, result manifests, sample expected outputs and Tabler source maps. They serve contract, provenance, example or licensed-distribution purposes.
- Credential/private-path review distinguishes task identifiers containing `sk-`, generic container home directories, placeholder paths and Zotero `/api/users/...` routes from secrets. No credential or personal absolute path is added. No outputs, PDFs, private corpus or new large binary is added.
- Historic root-path literals in the immutable baseline/session records remain historical references at their recorded commit; this table resolves their new locations. Active Markdown links are repaired. These deliberate historical literals are not live broken links.
- No project-level license exists. The bundled Tabler MIT notice remains intact; a project license awaits the maintainer's choice.

## Homepage structure and preserved detail

Before: 16 numbered sections, with overview, Demo, features, architecture, evaluation/provider tables, security, API endpoints, directory tree, six limitations and a roadmap.

After: positioning/languages/badges and current Tabler image; three reader benefits; a verifiable example; five-minute setup; workflow; three R1 highlights and frozen split design; engineering; privacy/reproducibility; documentation; one scope sentence; license status.

Full no-answer rates, development-only threshold limitations, Recall@5/@20, H007 overlap and failure analysis remain accessible through the [evaluation guide](../evaluation/README.md). Provider outcomes, truncation, budgets and replay evidence remain accessible through the [provider guide](../providers/README.md). The [documentation index](../README.md) covers current guides and the [archive](../archive/README.md) preserves prior presentation material.

## Validation

- After cleanup: **448 tracked candidate files, 12 root files, 7 top-level directories, 74 directories, 142 Markdown files, 12 images**. Five reader/audit indexes replace the redundant ZIP; all 20 moves are detected as renames. No new binary is added.
- All 142 Markdown files and 12 images are reachable from the bilingual homepages; 307 unique relative-link edges resolve, including homepage anchors. Historic path literals are retained only as provenance or in the explicit move record.
- All 317 source/configuration/lock/manifest/research blobs checked against the baseline are unchanged. Runtime, retrieval, Provider and formal evaluation semantics are unchanged.
- Targeted tests: 8 passed, 3 optional local-artifact tests skipped. `pip check`: no broken requirements. `git diff --check`: clean.
- Offline smoke: public-checkout UI/static and SSE succeed; missing assets produce the documented failure. With existing local assets, two complete frozen reports and one insufficient-evidence result replay with zero external calls; custom queries stay retrieval-only and online mode is rejected. All 17 original local corpus/artifact files remain byte-identical. External network connections were blocked during smoke.
- Initial full-suite execution on the Windows CRLF checkout: 557 passed, 36 failed, 5 skipped. Byte-stability/source-fingerprint failures came from system `core.autocrlf=true`; a preflight also requires a clean worktree. Final full-suite verification uses a clean detached copy with Git's original LF bytes, without changing any contract or relaxing a test.
- Clean LF full suite: **593 passed, 5 skipped**, with one existing Starlette/httpx deprecation warning. Skips require optional local artifacts; the separate offline smoke checks the installed frozen examples without committing them.

The PR records the final full-suite result, candidate commit, CI and rendered-GitHub evidence.
