from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from litflow.obsidian.checker import _strip_quotes, parse_frontmatter

START = "<!-- LITFLOW_STRUCTURED_READING_START -->"
END = "<!-- LITFLOW_STRUCTURED_READING_END -->"


def apply_obsidian_update(
    preview_path: Path,
    target_path: Path,
    manifest_path: Path,
    *,
    approved: bool = False,
    dry_run: bool = False,
    backup_dir: Path = Path("outputs/obsidian_backups"),
) -> dict[str, Any]:
    if approved and dry_run:
        raise ValueError("use either --approved or --dry-run, not both")
    if not approved and not dry_run:
        raise ValueError("apply-obsidian-update requires --approved to write, or --dry-run to preview")
    preview_text = preview_path.read_text(encoding="utf-8-sig")
    target_text = target_path.read_text(encoding="utf-8-sig")
    section_text = _extract_proposed_sections(preview_text)
    new_text, mode = _replace_marker_region(target_text, section_text)
    frontmatter_before = parse_frontmatter(target_text)
    frontmatter_after = parse_frontmatter(new_text)
    if frontmatter_before != frontmatter_after:
        raise ValueError("frontmatter would change; refusing to apply")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = backup_dir / f"{target_path.stem}.{timestamp}{target_path.suffix}"
    status = "dry_run_only" if dry_run else "applied"
    if approved:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_path, backup_path)
        target_path.write_text(new_text, encoding="utf-8")

    warnings: list[str] = []
    manifest = {
        "metadata": {
            "preview": str(preview_path),
            "target": str(target_path),
            "backup": str(backup_path) if approved else "",
            "applied": approved,
            "timestamp": timestamp,
        },
        "items": [
            {
                "zotero_key": _strip_quotes(frontmatter_before.get("zotero_key", "")),
                "target_note_path": str(target_path),
                "backup_path": str(backup_path) if approved else "",
                "status": status,
                "insert_mode": mode,
                "warnings": warnings,
            }
        ],
        "warnings": warnings,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _extract_proposed_sections(preview_text: str) -> str:
    marker = "## Proposed Reading Sections"
    if marker not in preview_text:
        raise ValueError("preview is missing '## Proposed Reading Sections'")
    return preview_text.split(marker, 1)[1].strip()


def _replace_marker_region(target_text: str, section_text: str) -> tuple[str, str]:
    region = f"{START}\n\n# AI 结构化精读\n\n{section_text}\n\n{END}"
    if START in target_text or END in target_text:
        if target_text.count(START) != 1 or target_text.count(END) != 1 or target_text.index(START) > target_text.index(END):
            raise ValueError("invalid litflow marker region")
        before, rest = target_text.split(START, 1)
        _, after = rest.split(END, 1)
        return before.rstrip() + "\n\n" + region + after, "append_or_replace_marker_region"
    return target_text.rstrip() + "\n\n" + region + "\n", "append_or_replace_marker_region"
