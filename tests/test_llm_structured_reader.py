import json

import pytest

from litflow.llm.client import LLMError, OpenAICompatibleClient
from litflow.llm.prompts import build_structured_reading_prompt
from litflow.llm.structured_reader import build_llm_input, read_paper_with_llm


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    def complete_json(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        return self.responses.pop(0)


def _clean_context():
    return {
        "metadata": {"zotero_key": "P1", "citation_key": "key2024", "title": "Paper"},
        "chunks": [
            {
                "chunk_id": "P1_chunk_0001",
                "page_start": 1,
                "page_end": 2,
                "section_guess": "abstract",
                "text": "The paper proposes a method.",
            },
            {
                "chunk_id": "P1_chunk_0002",
                "page_start": 3,
                "page_end": 4,
                "section_guess": "method",
                "text": "The second chunk contains geometry verification evidence.",
            }
        ],
        "annotations": {"items": []},
        "quality": {"warnings": []},
    }


def _valid_note():
    return {
        "zotero_key": "P1",
        "citation_key": "key2024",
        "title": "Paper",
        "reading_status": "llm_draft",
        "one_sentence_summary": "The paper proposes a method.",
        "research_background": "",
        "research_gap": "",
        "core_contribution": "",
        "method_summary": "",
        "data_or_experiment": "",
        "model_or_algorithm": "",
        "objective_or_task": "",
        "key_results": "",
        "limitations": "",
        "relevance_to_my_research": "",
        "usable_quotes_or_evidence": [],
        "related_concepts": [],
        "tags_suggestion": [],
        "evidence_links": [
            {
                "claim": "The paper proposes a method.",
                "chunk_id": "P1_chunk_0001",
                "page_start": 1,
                "page_end": 2,
                "evidence_text": "proposes a method",
            }
        ],
        "warnings": [],
    }


def test_clean_context_converts_to_llm_input_and_prompt_has_chunk_pages():
    llm_input = build_llm_input(_clean_context(), max_chunks=1)
    prompt = build_structured_reading_prompt(llm_input)

    assert llm_input["chunks"][0]["chunk_id"] == "P1_chunk_0001"
    assert llm_input["chunks"][0]["page_start"] == 1
    assert "P1_chunk_0001" in prompt
    assert "page_start" in prompt
    assert "Do not use external knowledge" in prompt


def test_mock_llm_valid_json_writes_structured_note(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    note = read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(_valid_note())]))

    assert note.zotero_key == "P1"
    assert json.loads(out.read_text(encoding="utf-8"))["evidence_links"][0]["chunk_id"] == "P1_chunk_0001"


def test_invalid_json_retries_and_succeeds(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    client = FakeLLM(["not json", json.dumps(_valid_note())])

    read_paper_with_llm(clean, out, client=client)

    assert client.calls == 2
    assert out.exists()


def test_json_code_fence_is_accepted(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    read_paper_with_llm(clean, out, client=FakeLLM([f"```json\n{json.dumps(_valid_note())}\n```"]))

    assert out.exists()


def test_evidence_error_retries_with_specific_reason(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    bad = _valid_note()
    bad["evidence_links"][0]["evidence_text"] = "not in the chunk"
    client = FakeLLM([json.dumps(bad), json.dumps(_valid_note())])

    read_paper_with_llm(clean, out, client=client)

    assert client.calls == 2
    assert "evidence_error_type=evidence_text_not_found" in client.prompts[1]


def test_invalid_json_after_retry_saves_error(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    with pytest.raises(LLMError):
        read_paper_with_llm(clean, out, client=FakeLLM(["bad", "still bad"]))

    error = json.loads(out.with_suffix(".error.json").read_text(encoding="utf-8"))
    assert error["raw_response"] == "still bad"
    assert error["error_type"] == "JSONDecodeError"


def test_evidence_link_unknown_chunk_fails(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    bad = _valid_note()
    bad["evidence_links"][0]["chunk_id"] = "missing"

    with pytest.raises(LLMError):
        read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(bad), json.dumps(bad)]))


def test_evidence_text_must_come_from_chunk(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    bad = _valid_note()
    bad["evidence_links"][0]["evidence_text"] = "not in the chunk"

    with pytest.raises(LLMError):
        read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(bad), json.dumps(bad)]))

    error = json.loads(out.with_suffix(".error.json").read_text(encoding="utf-8"))
    assert error["evidence_error_type"] == "evidence_text_not_found"
    assert error["failed_chunk_id"] == "P1_chunk_0001"
    assert error["candidate_chunk_id"] is None


def test_wrong_chunk_id_is_reported(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    bad = _valid_note()
    bad["evidence_links"][0]["evidence_text"] = "geometry verification evidence"

    with pytest.raises(LLMError):
        read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(bad), json.dumps(bad)]))

    error = json.loads(out.with_suffix(".error.json").read_text(encoding="utf-8"))
    assert error["evidence_error_type"] == "wrong_chunk_id"
    assert error["failed_chunk_id"] == "P1_chunk_0001"
    assert error["candidate_chunk_id"] == "P1_chunk_0002"


def test_page_range_mismatch_is_reported(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    bad = _valid_note()
    bad["evidence_links"][0]["page_end"] = 3

    with pytest.raises(LLMError):
        read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(bad), json.dumps(bad)]))

    error = json.loads(out.with_suffix(".error.json").read_text(encoding="utf-8"))
    assert error["evidence_error_type"] == "page_range_mismatch"
    assert error["failed_chunk_id"] == "P1_chunk_0001"


def test_missing_api_key_has_clear_error(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(LLMError) as exc:
        OpenAICompatibleClient.from_env()

    assert "Missing LLM environment variables" in str(exc.value)
