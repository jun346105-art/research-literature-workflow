from fastapi.testclient import TestClient

from litflow_api import app as api_app


client = TestClient(api_app.app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_evidence_candidate_bank_endpoint(monkeypatch):
    def fake_build(clean_context, out, report):
        return {
            "success": True,
            "metadata": {"chunk_count": 2, "anchored_count": 3},
            "failure_types": {},
            "anchoring_methods": {"exact_match": 3},
        }

    monkeypatch.setattr(api_app, "build_evidence_candidate_bank", fake_build)

    response = client.post(
        "/evidence-candidate-bank",
        json={"clean_context": "clean.json", "out": "bank.json", "report": "report.json"},
    )

    assert response.status_code == 200
    assert response.json()["candidate_bank_path"] == "bank.json"
    assert response.json()["metadata"]["anchored_count"] == 3


def test_structured_note_from_bank_endpoint(monkeypatch):
    class Note:
        zotero_key = "SAMPLE001"
        citation_key = "chen2026sample"
        evidence_links = [1, 2, 3]

    seen = {}

    def fake_generate(*args, **kwargs):
        seen.update(kwargs)
        return Note()

    monkeypatch.setattr(api_app, "generate_note_from_evidence_bank", fake_generate)

    response = client.post(
        "/structured-note-from-bank",
        json={
            "candidate_bank": "bank.json",
            "clean_context": "clean.json",
            "out": "note.json",
            "zotero_key": "SAMPLE001",
            "citation_key": "chen2026sample",
            "title": "Sample",
            "research_context": "sample project profile",
        },
    )

    assert response.status_code == 200
    assert response.json()["evidence_links_count"] == 3
    assert seen["research_context"] == "sample project profile"


def test_preview_update_endpoint(monkeypatch):
    def fake_preview(*args):
        return {
            "items": [
                {
                    "status": "preview_created",
                    "target_note_path": "target.md",
                    "preview_path": "preview.md",
                    "warnings": [],
                }
            ]
        }

    monkeypatch.setattr(api_app, "preview_obsidian_update", fake_preview)

    response = client.post(
        "/preview-obsidian-update",
        json={
            "structured_note": "note.json",
            "vault": "vault",
            "inbox": "00_Inbox/LiteratureReview",
            "out": "preview.md",
            "manifest": "manifest.json",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "preview_created"
    assert response.json()["manifest_path"] == "manifest.json"
