import json

import pytest

from litflow.llm.client import LLMError, OpenAICompatibleClient
from litflow.llm.prompts import build_structured_reading_prompt
from litflow.llm.structured_reader import _anchor_quote_hint, build_llm_input, read_paper_with_llm


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
    assert "quote_hint" in prompt


def test_mock_llm_valid_json_writes_structured_note(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")

    note = read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(_valid_note())]))

    assert note.zotero_key == "P1"
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["evidence_links"][0]["chunk_id"] == "P1_chunk_0001"
    assert saved["evidence_links"][0]["evidence_text"] in _clean_context()["chunks"][0]["text"]


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
    assert "evidence_anchor_error_type=evidence_anchor_not_found" in client.prompts[1]


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


def test_unanchorable_evidence_fails_and_saves_anchor_error(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    bad = _valid_note()
    bad["evidence_links"][0]["evidence_text"] = "not in the chunk"

    with pytest.raises(LLMError):
        read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(bad), json.dumps(bad)]))

    error = json.loads(out.with_suffix(".error.json").read_text(encoding="utf-8"))
    assert error["evidence_error_type"] == "evidence_anchor_not_found"
    assert error["failed_chunk_id"] == "P1_chunk_0001"
    assert error["anchor_failures"][0]["quote_hint"] == "not in the chunk"


def test_anchor_does_not_auto_fix_wrong_chunk_id(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    bad = _valid_note()
    bad["evidence_links"][0]["evidence_text"] = "geometry verification evidence"

    with pytest.raises(LLMError):
        read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(bad), json.dumps(bad)]))

    error = json.loads(out.with_suffix(".error.json").read_text(encoding="utf-8"))
    assert error["evidence_error_type"] == "evidence_anchor_not_found"
    assert error["failed_chunk_id"] == "P1_chunk_0001"
    assert error["anchor_failures"][0]["chunk_id"] == "P1_chunk_0001"


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


def test_anchor_quote_hint_exact_match():
    result = _anchor_quote_hint("proposes a method", "The paper proposes a method.")

    assert result["status"] == "ok"
    assert result["method"] == "exact_match"
    assert result["evidence_text"] == "proposes a method"


def test_anchor_quote_hint_normalized_whitespace_returns_original_span():
    chunk = "The paper proposes\na method with exact evidence."
    result = _anchor_quote_hint("paper proposes a method", chunk)

    assert result["status"] == "ok"
    assert result["method"] == "normalized_whitespace_match"
    assert result["evidence_text"] == "paper proposes\na method"
    assert result["evidence_text"] in chunk


def test_anchor_quote_hint_safe_mapping_preserves_original_span_and_rejects_space_hyphen():
    chunk = "The ﬁrst sample has a word-\ncontinuation."
    result = _anchor_quote_hint("The first sample has a wordcontinuation.", chunk)
    space_hyphen = _anchor_quote_hint("wordcontinuation", "word- continuation")

    assert result["status"] == "ok"
    assert result["method"] == "safe_normalized_match"
    assert result["evidence_text"] in chunk
    assert result["evidence_text"] == "The ﬁrst sample has a word-\ncontinuation"
    assert space_hyphen["status"] == "error"
    assert space_hyphen["error_type"] == "evidence_anchor_not_found"


def test_anchor_quote_hint_ambiguous_does_not_guess():
    result = _anchor_quote_hint("same phrase", "same phrase appears twice: same phrase")

    assert result["status"] == "error"
    assert result["error_type"] == "evidence_anchor_ambiguous"


def test_anchor_quote_hint_not_found():
    result = _anchor_quote_hint("missing phrase", "The paper proposes a method.")

    assert result["status"] == "error"
    assert result["error_type"] == "evidence_anchor_not_found"


def test_anchor_quote_hint_rejects_model_rewrite_and_non_contiguous_text():
    rewrite = _anchor_quote_hint("machine vision technology", "machine-vision based technology")
    non_contiguous = _anchor_quote_hint("alpha beta gamma delta", "alpha beta inserted gamma delta")

    assert rewrite["error_type"] == "evidence_anchor_not_found"
    assert non_contiguous["error_type"] == "evidence_anchor_not_found"


def test_unanchorable_too_few_valid_links_saves_error(tmp_path):
    clean = tmp_path / "clean.json"
    out = tmp_path / "note.json"
    clean.write_text(json.dumps(_clean_context()), encoding="utf-8")
    bad = _valid_note()
    bad["evidence_links"][0]["evidence_text"] = "missing phrase"

    with pytest.raises(LLMError):
        read_paper_with_llm(clean, out, client=FakeLLM([json.dumps(bad), json.dumps(bad)]))

    error = json.loads(out.with_suffix(".error.json").read_text(encoding="utf-8"))
    assert error["error_type"] == "EvidenceAnchoringError"
    assert error["anchor_failures"][0]["error_type"] == "evidence_anchor_not_found"


def test_missing_api_key_has_clear_error(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(LLMError) as exc:
        OpenAICompatibleClient.from_env()

    assert "Missing LLM environment variables" in str(exc.value)


def test_openai_compatible_client_sends_explicit_deepseek_non_thinking_json_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{}"}}]}'

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("litflow.llm.client.urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        base_url="https://api.deepseek.com",
        api_key="not-a-real-key",
        model="deepseek-v4-flash",
        thinking_mode="disabled",
    )

    client.complete_json_with_usage("Return JSON.", temperature=0, max_output_tokens=8192)

    assert captured["payload"]["model"] == "deepseek-v4-flash"
    assert captured["payload"]["temperature"] == 0
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["thinking"] == {"type": "disabled"}


def test_openai_compatible_client_sends_native_tool_payload_and_preserves_usage(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":null,"tool_calls":[{"id":"call_1","type":"function","function":{"name":"retrieve_evidence","arguments":"{\\"query\\":\\"WT-C3k2\\"}"}}]}}],"usage":{"prompt_tokens":12,"completion_tokens":3,"total_tokens":15}}'

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("litflow.llm.client.urlopen", fake_urlopen)
    client = OpenAICompatibleClient("https://api.deepseek.com", "not-a-real-key", "deepseek-v4-flash", "disabled")
    completion = client.complete_tools_with_usage(
        [{"role": "user", "content": "Choose a tool."}],
        [{"type": "function", "function": {"name": "retrieve_evidence", "description": "retrieve", "parameters": {"type": "object"}}}],
        temperature=0,
    )

    assert captured["payload"]["tools"][0]["function"]["name"] == "retrieve_evidence"
    assert captured["payload"]["tool_choice"] == "auto"
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert completion.tool_calls[0]["function"]["name"] == "retrieve_evidence"
    assert completion.input_tokens == 12
