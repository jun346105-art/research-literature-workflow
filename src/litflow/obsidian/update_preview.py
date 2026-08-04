from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from litflow.llm.models import StructuredReadingNote
from litflow.obsidian.checker import _strip_quotes, parse_frontmatter


def preview_obsidian_update(
    structured_note_path: Path,
    vault: Path,
    inbox: str,
    output_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    note = StructuredReadingNote.model_validate_json(structured_note_path.read_text(encoding="utf-8-sig"))
    target_note = _find_note_by_zotero_key(vault / inbox, note.zotero_key)
    warnings: list[str] = []
    status = "preview_created"

    if target_note is None:
        status = "target_note_missing"
        warnings.append(f"target note not found for zotero_key: {note.zotero_key}")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_render_preview(note, target_note), encoding="utf-8")

    manifest = {
        "metadata": {
            "structured_note": str(structured_note_path),
            "vault": str(vault),
            "inbox": inbox,
            "preview_count": 1 if status == "preview_created" else 0,
            "missing_target_count": 1 if status == "target_note_missing" else 0,
            "warnings_count": len(warnings),
        },
        "items": [
            {
                "zotero_key": note.zotero_key,
                "citation_key": note.citation_key,
                "title": note.title,
                "target_note_path": str(target_note) if target_note else "",
                "preview_path": str(output_path) if status == "preview_created" else "",
                "status": status,
                "warnings": warnings,
            }
        ],
        "warnings": warnings,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _find_note_by_zotero_key(note_dir: Path, zotero_key: str) -> Path | None:
    if not note_dir.exists():
        return None
    for note_path in sorted(note_dir.glob("*.md")):
        try:
            frontmatter = parse_frontmatter(note_path.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        if _strip_quotes(frontmatter.get("zotero_key", "")) == zotero_key:
            return note_path
    return None


def _render_preview(note: StructuredReadingNote, target_note: Path) -> str:
    evidence = "\n\n".join(
        [
            f"- Claim: {link.claim}\n"
            f"- Evidence:\n```text\n{link.evidence_text}\n```\n"
            f"- Source: `{link.chunk_id}`, pp. {link.page_start}-{link.page_end}"
            for link in note.evidence_links
        ]
    )
    tags = "\n".join(f"- {tag}" for tag in note.tags_suggestion) or "- not_found"
    warnings = "\n".join(f"- {warning}" for warning in note.warnings) or "- None"
    return f"""# Obsidian Update Preview: {note.title}

Target note:
{target_note}

## Proposed Reading Sections

## 1. 一句话结论

{note.one_sentence_summary}

## 2. 研究背景

{note.research_background}

## 3. 研究 Gap

{note.research_gap}

## 4. 核心创新点

{note.core_contribution}

## 5. 方法概述

{note.method_summary}

## 6. 数据 / 实验设置

{note.data_or_experiment}

## 7. 模型 / 算法 / 任务

- 模型 / 算法：{note.model_or_algorithm}
- 任务：{note.objective_or_task}

## 8. 关键结果

{note.key_results}

## 9. 局限性

{note.limitations}

## 10. 与我的研究的关系

{note.relevance_to_my_research}

## 11. 可引用证据

{evidence}

## 12. 建议标签

{tags}

## 13. Warnings

{warnings}
"""
