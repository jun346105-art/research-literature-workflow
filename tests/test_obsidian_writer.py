import json

from litflow.obsidian.checker import check_obsidian_notes
from litflow.obsidian.reconcile import plan_citekey_note_migration
from litflow.obsidian.writer import make_note_filename, write_obsidian_notes


def _snapshot(papers):
    return {"metadata": {"source": "zotero"}, "papers": papers}


def _paper(**overrides):
    data = {
        "zotero_key": "ABCD1234",
        "citation_key": "wang2024dynamicrouting",
        "title": "Dynamic Routing",
        "authors": ["Alice Wang", "Bob Li"],
        "year": 2024,
        "venue": "Journal",
        "doi": "10.1/demo",
        "url": "https://example.com",
        "abstract": "Abstract",
        "item_type": "journalArticle",
        "collection": "Research",
        "tags": ["rgbd"],
        "pdf_attachment_path": "C:/papers/a.pdf",
        "pdf_exists": True,
        "attachment_count": 1,
    }
    data.update(overrides)
    return data


def test_write_obsidian_notes_creates_markdown_with_citation_key(tmp_path):
    items = tmp_path / "zotero_collection.json"
    vault = tmp_path / "vault"
    manifest_path = tmp_path / "outputs" / "obsidian_note_manifest.json"
    items.write_text(json.dumps(_snapshot([_paper()])), encoding="utf-8")

    manifest = write_obsidian_notes(items, vault, "00_Inbox/LiteratureReview", manifest_path=manifest_path)
    note = vault / "00_Inbox" / "LiteratureReview" / "@wang2024dynamicrouting.md"

    assert note.exists()
    text = note.read_text(encoding="utf-8")
    assert 'citekey: "wang2024dynamicrouting"' in text
    assert 'zotero_key: "ABCD1234"' in text
    assert 'doi: "10.1/demo"' in text
    assert 'title: "Dynamic Routing"' in text
    assert 'authors: ["Alice Wang", "Bob Li"]' in text
    assert "year: 2024" in text
    assert 'venue: "Journal"' in text
    assert 'paper_type: "journalArticle"' in text
    assert 'reading_status: "inbox"' in text
    assert 'source: "zotero"' in text
    assert 'pdf_attachment_path: "C:/papers/a.pdf"' in text
    assert "pdf_exists: true" in text
    assert "attachment_count: 1" in text
    assert 'tags: ["rgbd"]' in text
    assert "# Dynamic Routing" in text
    assert "## 13. 关联文献" in text
    assert manifest["metadata"]["created_count"] == 1


def test_write_obsidian_notes_falls_back_to_zotero_key_without_citation_key(tmp_path):
    items = tmp_path / "zotero_collection.json"
    vault = tmp_path / "vault"
    items.write_text(json.dumps(_snapshot([_paper(citation_key=None)])), encoding="utf-8")

    write_obsidian_notes(items, vault, "00_Inbox/LiteratureReview", manifest_path=tmp_path / "manifest.json")

    assert (vault / "00_Inbox" / "LiteratureReview" / "@zotero_ABCD1234.md").exists()


def test_make_note_filename_cleans_windows_illegal_characters():
    assert make_note_filename(_paper(citation_key='bad\\/:*?"<>|key')) == "@bad_key.md"


def test_write_obsidian_notes_skips_existing_by_default(tmp_path):
    items = tmp_path / "zotero_collection.json"
    vault = tmp_path / "vault"
    note_dir = vault / "00_Inbox" / "LiteratureReview"
    note_dir.mkdir(parents=True)
    note = note_dir / "@wang2024dynamicrouting.md"
    note.write_text("existing", encoding="utf-8")
    items.write_text(json.dumps(_snapshot([_paper()])), encoding="utf-8")

    manifest = write_obsidian_notes(items, vault, "00_Inbox/LiteratureReview", manifest_path=tmp_path / "manifest.json")

    assert note.read_text(encoding="utf-8") == "existing"
    assert manifest["metadata"]["created_count"] == 0
    assert manifest["metadata"]["skipped_existing_count"] == 1
    assert manifest["notes"][0]["status"] == "skipped_existing_path"


def test_write_obsidian_notes_skips_existing_zotero_key_with_different_filename(tmp_path):
    items = tmp_path / "zotero_collection.json"
    vault = tmp_path / "vault"
    note_dir = vault / "00_Inbox" / "LiteratureReview"
    note_dir.mkdir(parents=True)
    (note_dir / "@zotero_ABCD1234.md").write_text(
        """---
zotero_key: "ABCD1234"
---
# Existing
""",
        encoding="utf-8",
    )
    items.write_text(json.dumps(_snapshot([_paper(citation_key="wang2024dynamicrouting")])), encoding="utf-8")

    manifest = write_obsidian_notes(items, vault, "00_Inbox/LiteratureReview", manifest_path=tmp_path / "manifest.json")

    assert not (note_dir / "@wang2024dynamicrouting.md").exists()
    assert manifest["metadata"]["created_count"] == 0
    assert manifest["metadata"]["skipped_existing_count"] == 1
    assert manifest["notes"][0]["status"] == "skipped_existing_zotero_key"


def test_write_obsidian_notes_overwrites_when_requested(tmp_path):
    items = tmp_path / "zotero_collection.json"
    vault = tmp_path / "vault"
    note_dir = vault / "00_Inbox" / "LiteratureReview"
    note_dir.mkdir(parents=True)
    note = note_dir / "@wang2024dynamicrouting.md"
    note.write_text("existing", encoding="utf-8")
    items.write_text(json.dumps(_snapshot([_paper()])), encoding="utf-8")

    manifest = write_obsidian_notes(
        items,
        vault,
        "00_Inbox/LiteratureReview",
        overwrite=True,
        manifest_path=tmp_path / "manifest.json",
    )

    assert "# Dynamic Routing" in note.read_text(encoding="utf-8")
    assert manifest["metadata"]["created_count"] == 1
    assert manifest["metadata"]["skipped_existing_count"] == 0


def test_manifest_records_created_skipped_and_failed(tmp_path):
    items = tmp_path / "zotero_collection.json"
    vault = tmp_path / "vault"
    note_dir = vault / "00_Inbox" / "LiteratureReview"
    note_dir.mkdir(parents=True)
    (note_dir / "@wang2024dynamicrouting.md").write_text("existing", encoding="utf-8")
    papers = [
        _paper(),
        _paper(zotero_key="EFGH5678", citation_key=None, title="New Paper"),
        _paper(zotero_key="", citation_key=None, title="Broken Paper"),
    ]
    items.write_text(json.dumps(_snapshot(papers)), encoding="utf-8")
    manifest_path = tmp_path / "outputs" / "obsidian_note_manifest.json"

    manifest = write_obsidian_notes(items, vault, "00_Inbox/LiteratureReview", manifest_path=manifest_path)
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["metadata"]["created_count"] == 1
    assert manifest["metadata"]["skipped_existing_count"] == 1
    assert manifest["metadata"]["failed_count"] == 1
    assert [note["status"] for note in saved["notes"]] == ["skipped_existing_path", "created", "failed"]
    assert saved["warnings"]


def test_check_obsidian_notes_reports_missing_fields_and_bad_pdf(tmp_path):
    vault = tmp_path / "vault"
    inbox = vault / "00_Inbox" / "LiteratureReview"
    inbox.mkdir(parents=True)
    (inbox / "@one.md").write_text(
        """---
citekey: "one"
zotero_key: "Z1"
title: "One"
authors: []
year: 2024
venue: ""
reading_status: "inbox"
source: "zotero"
pdf_attachment_path: "C:/missing.pdf"
pdf_exists: true
attachment_count: 1
---
# One
""",
        encoding="utf-8",
    )

    report = check_obsidian_notes(vault, "00_Inbox/LiteratureReview", tmp_path / "report.json")

    assert report["metadata"]["note_count"] == 1
    assert report["metadata"]["warning_count"] == 2
    assert any("missing required fields: doi" in warning for warning in report["warnings"])
    assert any("pdf_attachment_path does not exist" in warning for warning in report["warnings"])


def test_check_obsidian_notes_reports_duplicate_keys(tmp_path):
    vault = tmp_path / "vault"
    inbox = vault / "00_Inbox" / "LiteratureReview"
    inbox.mkdir(parents=True)
    body = """---
citekey: "dup"
zotero_key: "Z1"
doi: ""
title: "One"
authors: []
year: 2024
venue: ""
reading_status: "inbox"
source: "zotero"
pdf_attachment_path: ""
pdf_exists: false
attachment_count: 0
---
# One
"""
    (inbox / "@one.md").write_text(body, encoding="utf-8")
    (inbox / "@two.md").write_text(body.replace("title: \"One\"", "title: \"Two\""), encoding="utf-8")

    report = check_obsidian_notes(vault, "00_Inbox/LiteratureReview", tmp_path / "report.json")

    assert any("duplicate zotero_key: Z1" in warning for warning in report["warnings"])
    assert any("duplicate citekey: dup" in warning for warning in report["warnings"])


def test_plan_citekey_note_migration_reports_actions(tmp_path):
    items = tmp_path / "zotero_collection.json"
    vault = tmp_path / "vault"
    inbox = vault / "00_Inbox" / "LiteratureReview"
    inbox.mkdir(parents=True)
    (inbox / "@zotero_ABCD1234.md").write_text('---\nzotero_key: "ABCD1234"\n---\n', encoding="utf-8")
    (inbox / "@ok2024key.md").write_text('---\nzotero_key: "OK1"\n---\n', encoding="utf-8")
    (inbox / "@conflict2024key.md").write_text('---\nzotero_key: "OTHER"\n---\n', encoding="utf-8")
    (inbox / "@zotero_CONFLICT.md").write_text('---\nzotero_key: "CONFLICT"\n---\n', encoding="utf-8")
    papers = [
        _paper(zotero_key="ABCD1234", citation_key="wang2024dynamicrouting", title="Rename"),
        _paper(zotero_key="OK1", citation_key="ok2024key", title="OK"),
        _paper(zotero_key="MISSING", citation_key="missing2024key", title="Missing"),
        _paper(zotero_key="CONFLICT", citation_key="conflict2024key", title="Conflict"),
        _paper(zotero_key="NOKEY", citation_key=None, title="No Key"),
    ]
    items.write_text(json.dumps(_snapshot(papers)), encoding="utf-8")

    report = plan_citekey_note_migration(
        items,
        vault,
        "00_Inbox/LiteratureReview",
        tmp_path / "outputs" / "citekey_note_migration_plan.json",
    )

    actions = {plan["zotero_key"]: plan["action"] for plan in report["plans"]}
    assert actions["ABCD1234"] == "rename_recommended"
    assert actions["OK1"] == "already_ok"
    assert actions["MISSING"] == "missing_note"
    assert actions["CONFLICT"] == "conflict"
    assert actions["NOKEY"] == "citation_key_missing"
    assert report["metadata"]["needs_rename_count"] == 1
    assert report["metadata"]["already_ok_count"] == 1
    assert report["metadata"]["missing_note_count"] == 1
    assert report["metadata"]["conflict_count"] == 1
