import json

import pytest

from litflow.obsidian.apply_update import END, START, apply_obsidian_update


def _preview():
    return """# Obsidian Update Preview: Paper

Target note:
ignored

## Proposed Reading Sections

## 1. 一句话结论

Summary.

## 11. 可引用证据

- Claim: Claim.
- Evidence:
> Exact evidence
> with newline.
- Source: `P1_chunk_0001`, pp. 1-2
"""


def _target(body="# Existing\n\nUser content.\n"):
    return f"""---
zotero_key: "P1"
title: "Paper"
---
{body}"""


def test_apply_requires_approved_or_dry_run(tmp_path):
    preview = tmp_path / "preview.md"
    target = tmp_path / "target.md"
    preview.write_text(_preview(), encoding="utf-8")
    target.write_text(_target(), encoding="utf-8")

    with pytest.raises(ValueError):
        apply_obsidian_update(preview, target, tmp_path / "manifest.json")

    assert target.read_text(encoding="utf-8") == _target()


def test_apply_rejects_approved_and_dry_run_together(tmp_path):
    preview = tmp_path / "preview.md"
    target = tmp_path / "target.md"
    preview.write_text(_preview(), encoding="utf-8")
    target.write_text(_target(), encoding="utf-8")

    with pytest.raises(ValueError):
        apply_obsidian_update(preview, target, tmp_path / "manifest.json", approved=True, dry_run=True)


def test_dry_run_writes_manifest_without_modifying_target(tmp_path):
    preview = tmp_path / "preview.md"
    target = tmp_path / "target.md"
    manifest_path = tmp_path / "manifest.json"
    preview.write_text(_preview(), encoding="utf-8")
    original = _target()
    target.write_text(original, encoding="utf-8")

    manifest = apply_obsidian_update(preview, target, manifest_path, dry_run=True)

    assert target.read_text(encoding="utf-8") == original
    assert manifest["items"][0]["status"] == "dry_run_only"
    assert manifest["metadata"]["applied"] is False
    assert manifest_path.exists()


def test_apply_creates_backup_and_appends_marker_region(tmp_path):
    preview = tmp_path / "preview.md"
    target = tmp_path / "target.md"
    backup_dir = tmp_path / "backups"
    preview.write_text(_preview(), encoding="utf-8")
    original = _target()
    target.write_text(original, encoding="utf-8")

    manifest = apply_obsidian_update(preview, target, tmp_path / "manifest.json", approved=True, backup_dir=backup_dir)

    text = target.read_text(encoding="utf-8")
    assert text.startswith('---\nzotero_key: "P1"\ntitle: "Paper"\n---')
    assert "User content." in text
    assert START in text and END in text
    assert "# AI 结构化精读" in text
    assert "Exact evidence\n> with newline." in text
    backups = list(backup_dir.glob("*.md"))
    assert len(backups) == 1
    backup = backups[0]
    assert backup.read_text(encoding="utf-8") == original
    assert manifest["metadata"]["backup"] == str(backup)
    assert manifest["items"][0]["status"] == "applied"
    assert manifest["items"][0]["insert_mode"] == "append_or_replace_marker_region"


def test_apply_replaces_only_existing_marker_region(tmp_path):
    preview = tmp_path / "preview.md"
    target = tmp_path / "target.md"
    preview.write_text(_preview(), encoding="utf-8")
    original = _target(f"# Existing\n\nBefore.\n\n{START}\nold content\n{END}\n\nAfter.\n")
    target.write_text(original, encoding="utf-8")

    apply_obsidian_update(preview, target, tmp_path / "manifest.json", approved=True, backup_dir=tmp_path / "backups")

    text = target.read_text(encoding="utf-8")
    assert "Before." in text
    assert "After." in text
    assert "old content" not in text
    assert text.count(START) == 1
    assert text.count(END) == 1


def test_manifest_structure(tmp_path):
    preview = tmp_path / "preview.md"
    target = tmp_path / "target.md"
    manifest_path = tmp_path / "manifest.json"
    preview.write_text(_preview(), encoding="utf-8")
    target.write_text(_target(), encoding="utf-8")

    apply_obsidian_update(preview, target, manifest_path, approved=True, backup_dir=tmp_path / "backups")

    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["metadata"]["applied"] is True
    assert saved["items"][0]["zotero_key"] == "P1"
    assert saved["items"][0]["target_note_path"] == str(target)
    assert saved["items"][0]["backup_path"]
    assert saved["warnings"] == []
