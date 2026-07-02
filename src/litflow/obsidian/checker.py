from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = (
    "citekey",
    "zotero_key",
    "doi",
    "title",
    "authors",
    "year",
    "venue",
    "reading_status",
    "source",
    "pdf_attachment_path",
    "pdf_exists",
    "attachment_count",
)


def check_obsidian_notes(vault: Path, inbox: str, output_path: Path) -> dict[str, Any]:
    note_dir = vault / inbox
    notes = []
    warnings = []
    frontmatters: list[dict[str, str]] = []

    for note_path in sorted(note_dir.glob("*.md")) if note_dir.exists() else []:
        note = {"path": str(note_path), "status": "ok", "issues": []}
        try:
            frontmatter = parse_frontmatter(note_path.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            frontmatter = {}
            note["issues"].append(str(exc))
        missing = [field for field in REQUIRED_FIELDS if field not in frontmatter]
        if missing:
            note["issues"].append(f"missing required fields: {', '.join(missing)}")
        if frontmatter.get("reading_status") not in {'"inbox"', "inbox"}:
            note["issues"].append("reading_status is not inbox")
        pdf_path = _strip_quotes(frontmatter.get("pdf_attachment_path", ""))
        if pdf_path and not Path(pdf_path).exists():
            note["issues"].append("pdf_attachment_path does not exist")
        if note["issues"]:
            note["status"] = "warning"
        note["frontmatter"] = frontmatter
        notes.append(note)
        frontmatters.append(frontmatter)

    _add_duplicate_issues(notes, frontmatters, "zotero_key")
    _add_duplicate_issues(notes, frontmatters, "citekey")

    for note in notes:
        if note["issues"] and note["status"] == "ok":
            note["status"] = "warning"
        warnings.extend(f"{note['path']}: {issue}" for issue in note["issues"])

    report = {
        "metadata": {
            "vault": str(vault),
            "inbox": inbox,
            "note_count": len(notes),
            "warning_count": len(warnings),
            "read_only": True,
        },
        "notes": notes,
        "warnings": warnings,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML frontmatter")
    try:
        end = lines[1:].index("---") + 1
    except ValueError as exc:
        raise ValueError("unterminated YAML frontmatter") from exc

    data: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _add_duplicate_issues(notes: list[dict[str, Any]], frontmatters: list[dict[str, str]], field: str) -> None:
    values = [_strip_quotes(frontmatter.get(field, "")) for frontmatter in frontmatters]
    counts = Counter(value for value in values if value)
    duplicates = {value for value, count in counts.items() if count > 1}
    for note, value in zip(notes, values, strict=False):
        if value in duplicates:
            note["issues"].append(f"duplicate {field}: {value}")
            note["status"] = "warning"


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
