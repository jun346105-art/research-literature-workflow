import json

from litflow.llm.evidence_candidates import build_evidence_candidate_bank


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete_json(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)


def _clean_context():
    return {
        "chunks": [
            {
                "chunk_id": "P1_chunk_0001",
                "page_start": 1,
                "page_end": 1,
                "section_guess": "method",
                "text": "Alpha method extracts\nuseful evidence. Same phrase appears once.",
            },
            {
                "chunk_id": "P1_chunk_0002",
                "page_start": 2,
                "page_end": 2,
                "section_guess": "result",
                "text": "Repeated evidence. Repeated evidence.",
            },
            {
                "chunk_id": "P1_chunk_0003",
                "page_start": 3,
                "page_end": 3,
                "section_guess": "other",
                "text": "No matching phrase here.",
            },
        ]
    }


def _response(claim, quote_hint):
    return json.dumps({"candidates": [{"claim": claim, "quote_hint": quote_hint, "evidence_type": "method"}]})


def test_candidate_bank_fills_chunk_and_page_and_anchors_exact(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "bank.json"
    report = tmp_path / "report.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    build_evidence_candidate_bank(clean, out, report, client=FakeLLM([_response("claim", "Same phrase appears once."), '{"candidates":[]}', '{"candidates":[]}']))

    data = json.loads(out.read_text(encoding="utf-8"))
    candidate = data["candidates"][0]
    assert candidate["chunk_id"] == "P1_chunk_0001"
    assert candidate["page_start"] == 1
    assert candidate["page_end"] == 1
    assert candidate["evidence_text"] in _clean_context()["chunks"][0]["text"]
    assert "chunk_id" not in FakeLLM([_response("x", "y")]).responses[0]


def test_candidate_bank_normalized_whitespace_maps_to_original(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "bank.json"
    report = tmp_path / "report.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    build_evidence_candidate_bank(clean, out, report, client=FakeLLM([_response("claim", "method extracts useful evidence."), '{"candidates":[]}', '{"candidates":[]}']))

    candidate = json.loads(out.read_text(encoding="utf-8"))["candidates"][0]
    assert candidate["anchoring_method"] == "normalized_whitespace_match"
    assert candidate["evidence_text"] == "method extracts\nuseful evidence."


def test_candidate_bank_records_not_found_and_ambiguous(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "bank.json"
    report = tmp_path / "report.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    build_evidence_candidate_bank(
        clean,
        out,
        report,
        client=FakeLLM([_response("missing", "missing phrase"), _response("ambiguous", "Repeated evidence."), '{"candidates":[]}']),
    )

    data = json.loads(out.read_text(encoding="utf-8"))
    failures = data["failures"]
    assert failures[0]["error_type"] == "evidence_anchor_not_found"
    assert failures[1]["error_type"] == "evidence_anchor_ambiguous"
    assert all(c["evidence_text"] in _clean_context()["chunks"][0]["text"] for c in data["candidates"])
