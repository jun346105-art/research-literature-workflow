import json

import pytest

from litflow.pdf.extractor import extract_pdf_text
from litflow.reading_context import build_reading_contexts
from litflow.zotero.annotations import read_zotero_notes


class FakeAnnotationClient:
    def __init__(self, children):
        self.children = children

    def get_item_children(self, item_key):
        return self.children.get(item_key, [])


def _make_pdf(path, pages):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _snapshot(papers):
    return {"metadata": {"source": "zotero"}, "papers": papers}


def _paper(pdf_path, **overrides):
    data = {
        "zotero_key": "Z1",
        "citation_key": "key2024",
        "title": "Paper",
        "authors": ["Alice"],
        "year": 2024,
        "venue": "Journal",
        "doi": "10.1/demo",
        "abstract": "Abstract",
        "pdf_attachment_path": str(pdf_path) if pdf_path else "",
        "pdf_exists": bool(pdf_path),
    }
    data.update(overrides)
    return data


def test_extract_pdf_text_reads_existing_pdf(tmp_path):
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, ["hello page one", "hello page two"])

    result = extract_pdf_text(str(pdf))

    assert result.page_count == 2
    assert result.char_count > 0
    assert result.pages[0].page_number == 1
    assert "hello page one" in result.pages[0].text
    assert result.errors == []


def test_extract_pdf_text_missing_pdf_warns_without_crashing(tmp_path):
    result = extract_pdf_text(str(tmp_path / "missing.pdf"))

    assert result.page_count == 0
    assert result.errors == []
    assert result.warnings


def test_extract_pdf_text_invalid_pdf_records_error(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf", encoding="utf-8")

    result = extract_pdf_text(str(bad))

    assert result.errors


def test_extract_pdf_text_max_pages_limits_pages(tmp_path):
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, ["one", "two", "three"])

    result = extract_pdf_text(str(pdf), max_pages=2)

    assert result.page_count == 3
    assert len(result.pages) == 2
    assert any("limited to first 2 pages" in warning for warning in result.warnings)


def test_read_zotero_notes_handles_annotation_note_and_empty():
    client = FakeAnnotationClient(
        {
            "Z1": [
                {
                    "data": {
                        "itemType": "annotation",
                        "annotationText": "Highlighted text",
                        "annotationComment": "My comment",
                        "annotationPageLabel": "3",
                        "annotationColor": "#ffd400",
                        "dateModified": "2026-07-01",
                    }
                },
                {"data": {"itemType": "note", "note": "<p>Note text</p>", "dateModified": "2026-07-02"}},
            ],
            "Z2": [],
        }
    )

    notes = read_zotero_notes("Z1", client)
    empty = read_zotero_notes("Z2", client)

    assert notes["annotation_count"] == 1
    assert notes["note_count"] == 1
    assert notes["items"][0]["text"] == "Highlighted text"
    assert notes["items"][0]["comment"] == "My comment"
    assert empty["annotation_count"] == 0
    assert empty["note_count"] == 0


def test_build_reading_contexts_writes_per_paper_json_and_manifest(tmp_path):
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf, ["context text"])
    items = tmp_path / "zotero_collection.json"
    out_dir = tmp_path / "reading_context"
    manifest_path = tmp_path / "reading_context_manifest.json"
    items.write_text(json.dumps(_snapshot([_paper(pdf)])), encoding="utf-8")
    client = FakeAnnotationClient({"Z1": [{"data": {"itemType": "note", "note": "rough note"}}]})

    manifest = build_reading_contexts(items, out_dir, manifest_path, max_pages=1, zotero_client=client)
    context = json.loads((out_dir / "Z1.json").read_text(encoding="utf-8"))

    assert context["metadata"]["zotero_key"] == "Z1"
    assert context["pdf_text"]["page_count"] == 1
    assert context["pdf_text"]["char_count"] > 0
    assert context["zotero_notes"]["note_count"] == 1
    assert context["processing"]["status"] == "success"
    assert manifest["metadata"]["total_items"] == 1
    assert manifest["metadata"]["success_count"] == 1
    assert manifest["items"][0]["context_path"].endswith("Z1.json")


def test_build_reading_contexts_pdf_failure_does_not_block_other_papers(tmp_path):
    good = tmp_path / "good.pdf"
    bad = tmp_path / "bad.pdf"
    _make_pdf(good, ["good text"])
    bad.write_text("not a pdf", encoding="utf-8")
    items = tmp_path / "zotero_collection.json"
    out_dir = tmp_path / "reading_context"
    manifest_path = tmp_path / "reading_context_manifest.json"
    papers = [
        _paper(good, zotero_key="GOOD", citation_key="good2024"),
        _paper(bad, zotero_key="BAD", citation_key="bad2024"),
        _paper(tmp_path / "missing.pdf", zotero_key="MISS", citation_key="miss2024", pdf_exists=False),
    ]
    items.write_text(json.dumps(_snapshot(papers)), encoding="utf-8")

    manifest = build_reading_contexts(items, out_dir, manifest_path, zotero_client=FakeAnnotationClient({}))

    assert (out_dir / "GOOD.json").exists()
    assert (out_dir / "BAD.json").exists()
    assert (out_dir / "MISS.json").exists()
    assert manifest["metadata"]["total_items"] == 3
    assert manifest["metadata"]["success_count"] == 2
    assert manifest["metadata"]["missing_pdf_count"] == 1
    assert manifest["metadata"]["pdf_extract_failed_count"] == 1

