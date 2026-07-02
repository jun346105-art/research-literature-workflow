import json

from litflow.context.quality_gate import audit_clean_contexts, audit_one_clean_context


def _clean(**overrides):
    data = {
        "metadata": {"zotero_key": "Z1", "citation_key": "key2024", "title": "Paper"},
        "cleaning": {"page_count": 10, "cleaned_char_count": 10000},
        "chunks": [
            {"chunk_id": "c1", "char_count": 3500, "section_guess": "abstract"},
            {"chunk_id": "c2", "char_count": 3500, "section_guess": "introduction"},
            {"chunk_id": "c3", "char_count": 3000, "section_guess": "method"},
        ],
        "annotations": {"items": [], "aligned_count": 0},
        "quality": {"warnings": [], "errors": []},
    }
    data.update(overrides)
    return data


def test_ready_context_is_ready_for_llm():
    item = audit_one_clean_context(_clean(), "clean/Z1.json")

    assert item["quality_status"] == "ready_for_llm"
    assert item["section_distribution"] == {"abstract": 1, "introduction": 1, "method": 1}


def test_zero_chunks_is_failed():
    item = audit_one_clean_context(_clean(chunks=[]))

    assert item["quality_status"] == "failed"
    assert "chunk_count is 0" in item["warnings"]


def test_low_char_count_needs_manual_check_or_failed():
    item = audit_one_clean_context(_clean(cleaning={"page_count": 2, "cleaned_char_count": 2000}))

    assert item["quality_status"] == "needs_manual_check"
    assert "cleaned_char_count is below 3000" in item["warnings"]


def test_incomplete_warning_blocks_ready_for_llm():
    item = audit_one_clean_context(_clean(quality={"warnings": ["Phase 3A may have used max_pages; context may be incomplete"], "errors": []}))

    assert item["quality_status"] == "needs_manual_check"
    assert "max_pages/context incomplete warning detected" in item["warnings"]


def test_unknown_sections_warn():
    item = audit_one_clean_context(
        _clean(chunks=[{"chunk_id": "c1", "char_count": 4000, "section_guess": "unknown"}])
    )

    assert item["quality_status"] == "needs_manual_check"
    assert "all chunks have unknown section" in item["warnings"]
    assert "no key academic sections detected" in item["warnings"]


def test_unaligned_annotations_warn():
    item = audit_one_clean_context(_clean(annotations={"items": [{"type": "annotation"}], "aligned_count": 0}))

    assert item["quality_status"] == "needs_manual_check"
    assert "annotations exist but none aligned" in item["warnings"]


def test_references_ratio_warns():
    item = audit_one_clean_context(
        _clean(
            chunks=[
                {"chunk_id": "c1", "char_count": 3500, "section_guess": "references"},
                {"chunk_id": "c2", "char_count": 3500, "section_guess": "references"},
                {"chunk_id": "c3", "char_count": 3500, "section_guess": "introduction"},
            ]
        )
    )

    assert item["quality_status"] == "needs_manual_check"
    assert "references chunk ratio is above 50%" in item["warnings"]


def test_audit_report_stats(tmp_path):
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    (clean_dir / "Z1.json").write_text(json.dumps(_clean()), encoding="utf-8")
    (clean_dir / "Z2.json").write_text(json.dumps(_clean(metadata={"zotero_key": "Z2"}, chunks=[])), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "items": [
                    {"zotero_key": "Z1", "citation_key": "key1", "title": "One", "clean_context_path": str(clean_dir / "Z1.json")},
                    {"zotero_key": "Z2", "citation_key": "key2", "title": "Two", "clean_context_path": str(clean_dir / "Z2.json")},
                ]
            }
        ),
        encoding="utf-8",
    )

    report = audit_clean_contexts(clean_dir, manifest, tmp_path / "quality.json")

    assert report["metadata"]["total_items"] == 2
    assert report["metadata"]["ready_for_llm_count"] == 1
    assert report["metadata"]["failed_count"] == 1

