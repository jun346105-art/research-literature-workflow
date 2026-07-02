import json

from litflow.selection.export import export_zotero_import, load_selected_papers, make_citation_key
from litflow.selection.selector import build_selection_template, write_selection_template


def _candidate_pool():
    return {
        "schema_version": "1.0",
        "paper_count": 2,
        "papers": [
            {
                "title": "Dynamic Routing Optimization for RGBD Inspection",
                "authors": ["Wang Lei", "Alice Smith"],
                "year": 2024,
                "venue": "Journal of Packaging",
                "doi": "10.1000/demo",
                "url": "https://example.com/demo",
                "abstract": "A useful abstract.",
                "source": "OpenAlex",
                "citation_count": 10,
                "relevance_score": 0.9,
                "tier": "A",
                "search_query": "rgbd inspection",
                "recommended_bucket": "uncertain",
                "source_id": "demo",
                "keywords": ["rgbd"],
                "raw": {},
            },
            {
                "title": "Skipped Paper",
                "authors": ["Bob"],
                "year": 2023,
                "venue": None,
                "doi": None,
                "url": None,
                "abstract": None,
                "source": None,
                "citation_count": None,
                "relevance_score": None,
                "tier": None,
                "search_query": None,
                "recommended_bucket": "uncertain",
                "source_id": None,
                "keywords": [],
                "raw": {},
            },
        ],
    }


def test_build_selection_template_defaults_to_unselected(tmp_path):
    candidates = tmp_path / "candidate_pool.json"
    candidates.write_text(json.dumps(_candidate_pool()), encoding="utf-8")

    template = build_selection_template(candidates)

    assert template["metadata"]["total_candidates"] == 2
    assert template["metadata"]["selected_count"] == 0
    assert template["metadata"]["created_for_manual_review"] is True
    assert all(row["selected"] is False for row in template["papers"])
    assert template["papers"][0]["selection_reason"] == ""
    assert template["papers"][0]["manual_note"] == ""


def test_write_selection_template_creates_json(tmp_path):
    candidates = tmp_path / "candidate_pool.json"
    output = tmp_path / "selected_candidates.json"
    candidates.write_text(json.dumps(_candidate_pool()), encoding="utf-8")

    write_selection_template(candidates, output)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["papers"][0]["paper"]["title"].startswith("Dynamic")


def test_export_bibtex_only_exports_selected_papers(tmp_path):
    selected = tmp_path / "selected_candidates.json"
    output = tmp_path / "selected.bib"
    candidates = tmp_path / "candidate_pool.json"
    candidates.write_text(json.dumps(_candidate_pool()), encoding="utf-8")
    data = build_selection_template(candidates)
    data["papers"] = [
        {"selected": True, "selection_reason": "", "manual_note": "", "paper": _candidate_pool()["papers"][0]},
        {"selected": False, "selection_reason": "", "manual_note": "", "paper": _candidate_pool()["papers"][1]},
    ]
    selected.write_text(json.dumps(data), encoding="utf-8")

    count = export_zotero_import(selected, output, "bib")
    text = output.read_text(encoding="utf-8")

    assert count == 1
    assert "@article{wang2024dynamicroutingoptimization," in text
    assert "title = {Dynamic Routing Optimization for RGBD Inspection}" in text
    assert "author = {Wang Lei and Alice Smith}" in text
    assert "year = {2024}" in text
    assert "doi = {10.1000/demo}" in text
    assert "url = {https://example.com/demo}" in text
    assert "abstract = {A useful abstract.}" in text
    assert "Skipped Paper" not in text


def test_export_ris_contains_basic_fields(tmp_path):
    selected = tmp_path / "selected_candidates.json"
    output = tmp_path / "selected.ris"
    data = {
        "metadata": {},
        "papers": [
            {"selected": True, "selection_reason": "", "manual_note": "", "paper": _candidate_pool()["papers"][0]},
        ],
    }
    selected.write_text(json.dumps(data), encoding="utf-8")

    count = export_zotero_import(selected, output, "ris")
    text = output.read_text(encoding="utf-8")

    assert count == 1
    assert "TY  - JOUR" in text
    assert "TI  - Dynamic Routing Optimization for RGBD Inspection" in text
    assert "AU  - Wang Lei" in text
    assert "AU  - Alice Smith" in text
    assert "PY  - 2024" in text
    assert "JO  - Journal of Packaging" in text
    assert "DO  - 10.1000/demo" in text
    assert "UR  - https://example.com/demo" in text
    assert "AB  - A useful abstract." in text
    assert "ER  -" in text


def test_export_without_selected_papers_fails_without_output(tmp_path):
    selected = tmp_path / "selected_candidates.json"
    output = tmp_path / "selected.bib"
    data = {
        "metadata": {},
        "papers": [
            {"selected": False, "selection_reason": "", "manual_note": "", "paper": _candidate_pool()["papers"][0]},
        ],
    }
    selected.write_text(json.dumps(data), encoding="utf-8")

    try:
        export_zotero_import(selected, output, "bib")
    except ValueError as exc:
        assert "No papers with selected=true" in str(exc)
    else:
        raise AssertionError("expected no selected papers to fail")

    assert not output.exists()


def test_citation_key_is_stable():
    paper = _candidate_pool()["papers"][0]

    assert make_citation_key(paper) == "wang2024dynamicroutingoptimization"


def test_invalid_selected_candidates_json_fails(tmp_path):
    selected = tmp_path / "selected_candidates.json"
    selected.write_text(json.dumps({"papers": [{"selected": True}]}), encoding="utf-8")

    try:
        load_selected_papers(selected)
    except ValueError as exc:
        assert "invalid selected_candidates.json row 1" in str(exc)
    else:
        raise AssertionError("expected invalid selected_candidates.json to fail")
