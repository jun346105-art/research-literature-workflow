from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from litflow.obsidian.checker import parse_frontmatter, _strip_quotes
from litflow.obsidian.templates import render_literature_note

WINDOWS_ILLEGAL = r'[\\/:*?"<>|]'


def make_note_filename(paper: dict[str, Any]) -> str:
    citation_key = paper.get("citation_key")
    zotero_key = paper.get("zotero_key")
    if citation_key:
        stem = f"@{citation_key}"
    elif zotero_key:
        stem = f"@zotero_{zotero_key}"
    else:
        raise ValueError("paper is missing both citation_key and zotero_key")
    stem = _safe_windows_filename(stem)
    if not stem or stem == "@":
        raise ValueError("paper produced an empty note filename")
    return f"{stem}.md"


def write_obsidian_notes(
    items_path: Path,
    vault: Path,
    inbox: str,
    *,
    overwrite: bool = False,
    manifest_path: Path = Path("outputs/obsidian_note_manifest.json"),
) -> dict[str, Any]:
    data = json.loads(items_path.read_text(encoding="utf-8-sig"))
    papers = data.get("papers")
    if not isinstance(papers, list):
        raise ValueError("zotero_collection.json must contain a papers list")

    target_dir = vault / inbox
    target_dir.mkdir(parents=True, exist_ok=True)
    existing_by_zotero_key = _existing_notes_by_zotero_key(target_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    manifest = {
        "metadata": {
            "source": str(items_path),
            "vault": str(vault),
            "inbox": inbox,
            "created_count": 0,
            "skipped_existing_count": 0,
            "failed_count": 0,
        },
        "notes": [],
        "warnings": [],
    }

    for paper in papers:
        note = {
            "zotero_key": paper.get("zotero_key", ""),
            "citation_key": paper.get("citation_key"),
            "title": paper.get("title", ""),
            "note_path": "",
            "status": "failed",
        }
        try:
            note_path = target_dir / make_note_filename(paper)
            note["note_path"] = str(note_path)
            if note_path.exists() and not overwrite:
                note["status"] = "skipped_existing_path"
                manifest["metadata"]["skipped_existing_count"] += 1
            elif paper.get("zotero_key") in existing_by_zotero_key and not overwrite:
                existing_path = existing_by_zotero_key[paper.get("zotero_key")]
                note["note_path"] = str(existing_path)
                note["status"] = "skipped_existing_zotero_key"
                manifest["metadata"]["skipped_existing_count"] += 1
            else:
                note_path.write_text(render_literature_note(paper, today), encoding="utf-8")
                note["status"] = "created"
                manifest["metadata"]["created_count"] += 1
        except Exception as exc:
            manifest["metadata"]["failed_count"] += 1
            manifest["warnings"].append(f"{paper.get('title', '')}: {exc}")
        manifest["notes"].append(note)

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _safe_windows_filename(value: str) -> str:
    cleaned = re.sub(WINDOWS_ILLEGAL, "_", value).strip(" .")
    return re.sub(r"_+", "_", cleaned)


def _existing_notes_by_zotero_key(note_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for note_path in sorted(note_dir.glob("*.md")):
        try:
            frontmatter = parse_frontmatter(note_path.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        zotero_key = _strip_quotes(frontmatter.get("zotero_key", ""))
        if zotero_key and zotero_key not in index:
            index[zotero_key] = note_path
    return index
