import json

from litflow.context import clean_one_context, clean_reading_contexts
from litflow.context.annotation_aligner import align_annotations
from litflow.context.chunker import chunk_pages
from litflow.context.cleaner import clean_page_text
from litflow.context.models import CleanPage
from litflow.context.section_detector import detect_sections


def _context(pages, notes=None):
    return {
        "metadata": {
            "zotero_key": "Z1",
            "citation_key": "key2024",
            "title": "Paper",
            "authors": ["Alice"],
            "year": 2024,
            "doi": "10.1/demo",
            "pdf_attachment_path": "C:/paper.pdf",
        },
        "pdf_text": {
            "page_count": len(pages),
            "char_count": sum(len(page["text"]) for page in pages),
            "pages": pages,
            "warnings": [],
            "errors": [],
        },
        "zotero_notes": notes or {"annotation_count": 0, "note_count": 0, "items": [], "warnings": []},
        "processing": {"status": "success", "warnings": [], "errors": []},
    }


def test_clean_page_text_preserves_content_and_fixes_hyphenation():
    page = clean_page_text({"page_number": 1, "text": "  optimiza-\ntion\n\n\nkeeps formula x=y  "})

    assert "optimization" in page.text
    assert "keeps formula x=y" in page.text
    assert "\n\n\n" not in page.text
    assert page.page_number == 1


def test_chunk_pages_skips_empty_pages_and_short_text_gets_one_chunk():
    pages = [
        CleanPage(page_number=1, text="", original_char_count=0, cleaned_char_count=0),
        CleanPage(page_number=2, text="short text", original_char_count=10, cleaned_char_count=10),
    ]

    chunks = chunk_pages(pages, zotero_key="Z1", citation_key="key", title="T", chunk_size_chars=3500, chunk_overlap_chars=400)

    assert len(chunks) == 1
    assert chunks[0].page_start == 2
    assert chunks[0].page_end == 2
    assert chunks[0].source_page_numbers == [2]


def test_chunk_pages_overlap_does_not_loop_forever():
    pages = [CleanPage(page_number=1, text="a" * 100, original_char_count=100, cleaned_char_count=100)]

    chunks = chunk_pages(pages, zotero_key="Z1", citation_key="key", title="T", chunk_size_chars=30, chunk_overlap_chars=29)

    assert len(chunks) <= 100
    assert chunks[0].page_start == 1


def test_detect_sections_basic_headings():
    pages = [
        CleanPage(page_number=1, text="Abstract\nThis is abstract.", original_char_count=26, cleaned_char_count=26),
        CleanPage(page_number=2, text="1. Introduction\nText.", original_char_count=21, cleaned_char_count=21),
        CleanPage(page_number=3, text="References\n[1]", original_char_count=14, cleaned_char_count=14),
    ]

    detected, sections = detect_sections(pages)

    assert [page.section_guess for page in detected] == ["abstract", "introduction", "references"]
    assert [section["section_guess"] for section in sections] == ["abstract", "introduction", "references"]


def test_align_annotations_to_page_chunk_global_and_unaligned():
    pages = [
        CleanPage(page_number=1, text="This page has highlighted text.", original_char_count=31, cleaned_char_count=31),
    ]
    chunks = chunk_pages(pages, zotero_key="Z1", citation_key="key", title="T", chunk_size_chars=100, chunk_overlap_chars=0)
    notes = {
        "items": [
            {"type": "annotation", "text": "highlighted text", "comment": "c"},
            {"type": "note", "text": "global note"},
            {"type": "annotation", "text": "not present"},
        ]
    }

    aligned, updated_chunks = align_annotations(notes, pages, chunks)

    assert aligned["items"][0]["alignment_status"] == "matched"
    assert aligned["items"][0]["matched_page"] == 1
    assert aligned["items"][0]["matched_chunk_id"] == "Z1_chunk_0001"
    assert aligned["items"][1]["alignment_status"] == "global_note"
    assert aligned["items"][2]["alignment_status"] == "unaligned"
    assert updated_chunks[0].contains_annotation is True


def test_clean_one_context_structure_and_quality_warnings():
    context = _context(
        [{"page_number": 1, "text": "References\n" + "x" * 1200}],
        {"items": [{"type": "annotation", "text": "missing annotation"}], "warnings": []},
    )
    context["processing"]["warnings"] = ["extraction limited to first 5 pages"]

    clean = clean_one_context(context, chunk_size=500, overlap=50)

    assert clean["metadata"]["zotero_key"] == "Z1"
    assert clean["cleaning"]["cleaned_char_count"] > 1000
    assert clean["sections"][0]["section_guess"] == "references"
    assert clean["chunks"]
    assert clean["annotations"]["unaligned_count"] == 1
    assert "references section detected" in clean["quality"]["warnings"]
    assert "Phase 3A may have used max_pages; context may be incomplete" in clean["quality"]["warnings"]


def test_clean_reading_contexts_manifest_stats(tmp_path):
    context_dir = tmp_path / "reading_context"
    out_dir = tmp_path / "clean_reading_context"
    context_dir.mkdir()
    context_path = context_dir / "Z1.json"
    context_path.write_text(
        json.dumps(_context([{"page_number": 1, "text": "Abstract\n" + "a" * 1200}])),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "reading_context_manifest.json"
    manifest_path.write_text(
        json.dumps({"items": [{"zotero_key": "Z1", "citation_key": "key2024", "title": "Paper", "context_path": str(context_path)}]}),
        encoding="utf-8",
    )

    manifest = clean_reading_contexts(
        context_dir,
        manifest_path,
        out_dir,
        tmp_path / "clean_reading_context_manifest.json",
        chunk_size=500,
        overlap=50,
    )

    assert manifest["metadata"]["total_items"] == 1
    assert manifest["metadata"]["success_count"] == 1
    assert manifest["metadata"]["total_chunks"] >= 1
    assert manifest["items"][0]["clean_context_path"].endswith("Z1.json")

