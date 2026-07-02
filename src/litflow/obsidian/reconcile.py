from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from litflow.obsidian.checker import _strip_quotes, parse_frontmatter
from litflow.obsidian.writer import make_note_filename


def plan_citekey_note_migration(items_path: Path, vault: Path, inbox: str, output_path: Path) -> dict[str, Any]:
    data = json.loads(items_path.read_text(encoding="utf-8-sig"))
    papers = data.get("papers")
    if not isinstance(papers, list):
        raise ValueError("zotero_collection.json must contain a papers list")

    note_dir = vault / inbox
    existing_notes = _scan_existing_notes(note_dir)
    plans = []
    warnings = []

    for paper in papers:
        plan = _plan_one(paper, note_dir, existing_notes, warnings)
        plans.append(plan)

    counts = {
        "items": len(papers),
        "existing_notes": len(existing_notes["paths"]),
        "needs_rename_count": sum(1 for plan in plans if plan["action"] == "rename_recommended"),
        "already_ok_count": sum(1 for plan in plans if plan["action"] == "already_ok"),
        "missing_note_count": sum(1 for plan in plans if plan["action"] == "missing_note"),
        "conflict_count": sum(1 for plan in plans if plan["action"] == "conflict"),
    }
    report = {"metadata": counts, "plans": plans, "warnings": warnings}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _plan_one(
    paper: dict[str, Any],
    note_dir: Path,
    existing_notes: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    citation_key = paper.get("citation_key")
    zotero_key = paper.get("zotero_key") or ""
    current_path = existing_notes["by_zotero_key"].get(zotero_key)
    target_path = ""
    action = "missing_note"
    reason = "No existing note for this zotero_key."

    if not citation_key:
        action = "citation_key_missing"
        reason = "No citation_key in Zotero snapshot."
    else:
        target_path_obj = note_dir / make_note_filename(paper)
        target_path = str(target_path_obj)
        if "$" in citation_key:
            warnings.append(f"{zotero_key}: citation_key contains '$'; filename keeps it unchanged.")
        if current_path and Path(current_path) == target_path_obj:
            action = "already_ok"
            reason = "Existing note already uses the citation_key filename."
        elif current_path and target_path_obj.exists():
            action = "conflict"
            reason = "Existing note for zotero_key and target citation_key filename both exist."
        elif current_path:
            action = "rename_recommended"
            reason = "Existing note uses a non-citation-key filename."
        elif target_path_obj.exists():
            action = "conflict"
            reason = "Target citation_key filename exists but no note with this zotero_key was found."

    return {
        "zotero_key": zotero_key,
        "citation_key": citation_key,
        "title": paper.get("title", ""),
        "current_note_path": str(current_path or ""),
        "target_note_path": target_path,
        "action": action,
        "reason": reason,
    }


def _scan_existing_notes(note_dir: Path) -> dict[str, Any]:
    by_zotero_key: dict[str, Path] = {}
    paths: list[Path] = []
    for note_path in sorted(note_dir.glob("*.md")) if note_dir.exists() else []:
        paths.append(note_path)
        try:
            frontmatter = parse_frontmatter(note_path.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        zotero_key = _strip_quotes(frontmatter.get("zotero_key", ""))
        if zotero_key and zotero_key not in by_zotero_key:
            by_zotero_key[zotero_key] = note_path
    return {"by_zotero_key": by_zotero_key, "paths": paths}

