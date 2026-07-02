import json

from litflow.obsidian.update_preview import preview_obsidian_update


def _structured_note(**overrides):
    data = {
        "zotero_key": "P1",
        "citation_key": "key2024",
        "title": "Paper",
        "reading_status": "llm_draft",
        "one_sentence_summary": "One sentence.",
        "research_background": "Background.",
        "research_gap": "Gap.",
        "core_contribution": "Contribution.",
        "method_summary": "Method.",
        "data_or_experiment": "Data.",
        "model_or_algorithm": "Model.",
        "objective_or_task": "Task.",
        "key_results": "Results.",
        "limitations": "Limitations.",
        "relevance_to_my_research": "",
        "usable_quotes_or_evidence": [],
        "related_concepts": [],
        "tags_suggestion": ["tag1", "tag2"],
        "evidence_links": [
            {
                "claim": "Claim.",
                "chunk_id": "P1_chunk_0001",
                "page_start": 1,
                "page_end": 2,
                "evidence_text": "Exact evidence\nwith newline.",
            }
        ],
        "warnings": [],
    }
    data.update(overrides)
    return data


def test_preview_obsidian_update_creates_markdown_and_manifest(tmp_path):
    structured = tmp_path / "structured.json"
    vault = tmp_path / "vault"
    inbox = vault / "00_Inbox" / "LiteratureReview"
    note = inbox / "@zotero_P1.md"
    out = tmp_path / "outputs" / "preview.md"
    manifest_path = tmp_path / "outputs" / "manifest.json"
    inbox.mkdir(parents=True)
    original_note = '---\nzotero_key: "P1"\n---\n# Existing\n'
    note.write_text(original_note, encoding="utf-8")
    structured.write_text(json.dumps(_structured_note()), encoding="utf-8")

    manifest = preview_obsidian_update(structured, vault, "00_Inbox/LiteratureReview", out, manifest_path)

    text = out.read_text(encoding="utf-8")
    assert "# Obsidian Update Preview: Paper" in text
    assert str(note) in text
    assert "Exact evidence\n> with newline." in text
    assert "`P1_chunk_0001`, pp. 1-2" in text
    assert note.read_text(encoding="utf-8") == original_note
    assert manifest["metadata"]["preview_count"] == 1
    assert manifest["items"][0]["status"] == "preview_created"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["items"][0]["target_note_path"] == str(note)


def test_preview_obsidian_update_missing_target_warns_without_creating_note(tmp_path):
    structured = tmp_path / "structured.json"
    vault = tmp_path / "vault"
    out = tmp_path / "outputs" / "preview.md"
    manifest_path = tmp_path / "outputs" / "manifest.json"
    structured.write_text(json.dumps(_structured_note()), encoding="utf-8")

    manifest = preview_obsidian_update(structured, vault, "00_Inbox/LiteratureReview", out, manifest_path)

    assert not out.exists()
    assert not vault.exists()
    assert manifest["metadata"]["preview_count"] == 0
    assert manifest["metadata"]["missing_target_count"] == 1
    assert manifest["items"][0]["status"] == "target_note_missing"
    assert manifest["warnings"]
