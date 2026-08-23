from __future__ import annotations

import json

import pytest

from litflow.llm.client import LLMCompletion
from litflow.rag.qa import CanonicalTransportError, RawAnswer, RawAnswerV11, SAFE_EXECUTION_FAILURE_ZH, TransportError, _parse_transport, _parse_v11, _render_answer_v11, _verify, _verify_v11, evaluate_qa, plan_qa, plan_qa_v11, replay_qa_v11, replay_qa_transport, run_qa, run_qa_v11, write_qa_review_packet


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def complete_json_with_usage(self, _prompt, **_kwargs):
        self.calls += 1
        return LLMCompletion(json.dumps(self.response), input_tokens=10, output_tokens=5, total_tokens=15)


def test_answer_contract_and_quote_validation():
    with pytest.raises(Exception):
        RawAnswer.model_validate({"status": "answered", "claims": [], "limitations_zh": ""})
    passages = {"P1:P1_chunk_0001": {"text": "alpha evidence", "page_start": 1, "page_end": 1}}
    raw = RawAnswer.model_validate({"status": "answered", "claims": [{"claim_text_zh": "回答", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""})
    assert _verify("Q1", raw, passages, ["P1:P1_chunk_0001"], []).execution_status == "success"
    bad = RawAnswer.model_validate({"status": "answered", "claims": [{"claim_text_zh": "回答", "citations": [{"passage_id": "P2:missing", "evidence_quote": "alpha"}]}], "limitations_zh": ""})
    assert _verify("Q1", bad, passages, ["P1:P1_chunk_0001"], []).execution_status == "citation_validation_failed"


def test_transport_envelope_validation_and_strict_domain_contract():
    query = {"query_id": "Q1", "query_zh": "中文 问题"}
    direct, ledger = _parse_transport(json.dumps({"status": "insufficient_evidence", "claims": [], "limitations_zh": ""}), query)
    assert direct.status == "insufficient_evidence" and ledger["envelope_unwrapped"] is False
    wrapped = {"query_id": "Q1", "query_zh": "中文\n问题", "schema": {"status": "answered", "claims": [], "limitations_zh": ""}}
    with pytest.raises(TransportError, match="strict schema"):
        _parse_transport(json.dumps(wrapped), query)
    wrapped["query_id"] = "Q2"
    with pytest.raises(TransportError, match="query_id mismatch"):
        _parse_transport(json.dumps(wrapped), query)
    with pytest.raises(TransportError, match="unknown transport"):
        _parse_transport(json.dumps({"status": "answered", "claims": [], "limitations_zh": "", "extra": 1}), query)


def test_qa_runner_no_qrels_in_prompt_and_resume(tmp_path):
    corpus, queries = _inputs(tmp_path)
    client = FakeClient({"status": "answered", "claims": [{"claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""})
    run = run_qa(corpus, queries, tmp_path / "run", model="fake", client=client)
    assert len(run["results"]) == 2
    assert client.calls == 2
    assert plan_qa(corpus, queries, model="fake")["top_k"] == 10
    run_qa(corpus, queries, tmp_path / "run", model="fake", client=client, resume=True)
    assert client.calls == 2
    report = evaluate_qa(tmp_path / "run", corpus, queries, tmp_path / "report.json")
    assert report["false_answer_count"] == 0
    assert report["execution_failure_count"] == 1


def test_offline_replay_uses_main_before_repair_and_never_constructs_client(tmp_path, monkeypatch):
    corpus, queries = _inputs(tmp_path)
    source = tmp_path / "source"; (source / "queries" / "Q1").mkdir(parents=True); (source / "queries" / "Q2").mkdir(parents=True); (source / "retrieval").mkdir()
    for query_id in ["Q1", "Q2"]:
        (source / "retrieval" / f"{query_id}.json").write_text(json.dumps(["P1:P1_chunk_0001"]), encoding="utf-8")
    valid = {"query_id": "Q1", "query_zh": "alpha", "schema": {"status": "answered", "claims": [{"claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""}}
    (source / "queries" / "Q1" / "raw_response_attempt_1.txt").write_text(json.dumps(valid), encoding="utf-8")
    (source / "queries" / "Q1" / "raw_response_attempt_2.txt").write_text("{}", encoding="utf-8")
    bad = {"query_id": "Q2", "query_zh": "unknown", "schema": {"status": "answered", "claims": [], "limitations_zh": ""}}
    (source / "queries" / "Q2" / "raw_response_attempt_1.txt").write_text(json.dumps(bad), encoding="utf-8")
    (source / "queries" / "Q2" / "raw_response_attempt_2.txt").write_text(json.dumps({"status": "insufficient_evidence", "claims": [], "limitations_zh": ""}), encoding="utf-8")
    replay = replay_qa_transport(source, corpus, queries, tmp_path / "replay")
    assert replay["results"][0].execution_status == "success"
    assert replay["results"][1].answer_status == "insufficient_evidence"
    assert (tmp_path / "replay" / "replay_manifest.json").is_file()


def test_review_packet_contains_only_verified_answered_results(tmp_path):
    corpus, queries = _inputs(tmp_path)
    client = FakeClient({"status": "answered", "claims": [{"claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""})
    run_qa(corpus, queries, tmp_path / "run", model="fake", client=client)
    packet = tmp_path / "verified_packet.md"
    write_qa_review_packet(tmp_path / "run", corpus, packet)
    rendered = packet.read_text(encoding="utf-8")
    assert "## Q1" in rendered
    assert "## Q2" not in rendered


def test_v11_accepts_only_canonical_transport_payload():
    query = {"query_id": "Q1", "query_zh": "alpha"}
    canonical = {"status": "insufficient_evidence", "claims": [], "limitations_zh": "evidence is limited"}
    assert _parse_v11(json.dumps(canonical)).status == "insufficient_evidence"
    wrapped = {"query_id": "Q1", "query_zh": "alpha", "schema": canonical}
    with pytest.raises(CanonicalTransportError, match="canonical top-level"):
        _parse_v11(json.dumps(wrapped))
    with pytest.raises(CanonicalTransportError, match="canonical top-level"):
        _parse_v11(json.dumps({**canonical, "data": {}}))


def test_v11_requires_subject_paper_and_matching_citation_paper():
    passages = {
        "P1:P1_chunk_0001": {"text": "alpha evidence", "page_start": 1, "page_end": 1, "paper_key": "P1", "title": "Paper One", "citation_key": "one"},
        "P2:P2_chunk_0001": {"text": "beta evidence", "page_start": 2, "page_end": 2, "paper_key": "P2", "title": "Paper Two", "citation_key": "two"},
    }
    raw = RawAnswerV11.model_validate({"status": "answered", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "alpha", "citations": [{"passage_id": "P2:P2_chunk_0001", "evidence_quote": "beta evidence"}]}], "limitations_zh": ""})
    result = _verify_v11("Q1", raw, passages, ["P1:P1_chunk_0001", "P2:P2_chunk_0001"], [])
    assert result.execution_status == "citation_validation_failed"
    assert result.validation_error == "citation paper_key does not match subject_paper_key"
    unknown_subject = RawAnswerV11.model_validate({"status": "answered", "claims": [{"subject_paper_key": "P3", "claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""})
    assert _verify_v11("Q1", unknown_subject, passages, ["P1:P1_chunk_0001", "P2:P2_chunk_0001"], []).validation_error == "subject_paper_key is not in this query top-10"


def test_v11_quote_validation_and_deterministic_rendering_deduplicate_passages():
    passages = {
        "P1:P1_chunk_0001": {"text": "alpha evidence", "page_start": 1, "page_end": 1, "paper_key": "P1", "title": "Paper One", "citation_key": "one"},
    }
    raw = RawAnswerV11.model_validate({"status": "answered", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}, {"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""})
    result = _verify_v11("Q1", raw, passages, ["P1:P1_chunk_0001"], [])
    assert result.execution_status == "success"
    assert result.claims[0]["citations"] == [result.claims[0]["citations"][0]]
    rendered = _render_answer_v11(result.claims, passages)
    assert rendered.startswith("根据当前检索到的证据，可以确认：")
    assert rendered.count("P1:P1_chunk_0001") == 1
    paraphrase = RawAnswerV11.model_validate({"status": "answered", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha paraphrase"}]}], "limitations_zh": ""})
    assert _verify_v11("Q1", paraphrase, passages, ["P1:P1_chunk_0001"], []).execution_status == "quote_grounding_failed"


def test_v11_canary_executes_only_selected_query_without_retry(tmp_path):
    corpus, queries = _inputs(tmp_path)
    response = {"status": "answered", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""}
    client = FakeClient(response)
    plan = plan_qa_v11(corpus, queries, model="fake", query_id="Q1")
    assert plan["query_count"] == 1
    assert plan["maximum_calls"] == 1
    run = run_qa_v11(corpus, queries, tmp_path / "canary", model="fake", query_id="Q1", client=client)
    assert client.calls == 1
    assert [result.query_id for result in run["results"]] == ["Q1"]
    assert run["results"][0].execution_status == "success"
    wrapped_client = FakeClient({"query_id": "Q1", "query_zh": "alpha", "schema": response})
    failed = run_qa_v11(corpus, queries, tmp_path / "failed_canary", model="fake", query_id="Q1", client=wrapped_client)
    assert wrapped_client.calls == 1
    assert failed["results"][0].execution_status == "transport_failed"


def test_v11_allows_only_duplicate_identical_quote_in_declared_passage():
    passages = {
        "P1:P1_chunk_0001": {"text": "alpha evidence then alpha evidence", "page_start": 1, "page_end": 1, "paper_key": "P1", "title": "Paper One", "citation_key": "one"},
    }
    raw = RawAnswerV11.model_validate({"status": "answered", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""})
    result = _verify_v11("Q1", raw, passages, ["P1:P1_chunk_0001"], [])
    citation = result.claims[0]["citations"][0]
    assert result.execution_status == "success"
    assert citation["anchor_status"] == "grounded_multiple_identical_occurrences"
    assert citation["match_count"] == 2
    assert citation["selected_offset"] == 0
    assert result.quote_grounding_ledger[0]["ambiguity_preserved"] is True
    assert len(result.quote_grounding_ledger[0]["matches"]) == 2


def test_v11_rejects_duplicate_quote_when_it_exists_in_another_passage_or_paper():
    passages = {
        "P1:P1_chunk_0001": {"text": "alpha evidence then alpha evidence", "page_start": 1, "page_end": 1, "paper_key": "P1", "title": "Paper One", "citation_key": "one"},
        "P2:P2_chunk_0001": {"text": "alpha evidence", "page_start": 2, "page_end": 2, "paper_key": "P2", "title": "Paper Two", "citation_key": "two"},
    }
    raw = RawAnswerV11.model_validate({"status": "answered", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""})
    result = _verify_v11("Q1", raw, passages, ["P1:P1_chunk_0001"], [])
    assert result.execution_status == "quote_grounding_failed"
    assert result.validation_error == "evidence_anchor_ambiguous"
    assert result.quote_grounding_ledger[0]["classification"] == "matches_across_papers"


def test_v11_rejects_duplicate_quote_when_it_exists_in_another_passage_of_same_paper():
    passages = {
        "P1:P1_chunk_0001": {"text": "alpha evidence then alpha evidence", "page_start": 1, "page_end": 1, "paper_key": "P1", "title": "Paper One", "citation_key": "one"},
        "P1:P1_chunk_0002": {"text": "alpha evidence", "page_start": 2, "page_end": 2, "paper_key": "P1", "title": "Paper One", "citation_key": "one"},
    }
    raw = RawAnswerV11.model_validate({"status": "answered", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""})
    result = _verify_v11("Q1", raw, passages, ["P1:P1_chunk_0001"], [])
    assert result.execution_status == "quote_grounding_failed"
    assert result.quote_grounding_ledger[0]["classification"] == "matches_across_passages"


def test_v11_ambiguity_replay_is_offline_and_preserves_source_raw(tmp_path, monkeypatch):
    corpus, queries = _inputs(tmp_path)
    source = tmp_path / "source"
    raw = {"status": "answered", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "alpha", "citations": [{"passage_id": "P1:P1_chunk_0001", "evidence_quote": "alpha evidence"}]}], "limitations_zh": ""}
    (source / "queries" / "Q1").mkdir(parents=True)
    raw_path = source / "queries" / "Q1" / "raw_response_attempt_1.txt"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    (source / "queries" / "Q1" / "checkpoint_1.json").write_text(json.dumps({"raw_sha256": __import__("hashlib").sha256(raw_path.read_bytes()).hexdigest()}), encoding="utf-8")
    (source / "retrieval").mkdir()
    (source / "retrieval" / "Q1.json").write_text(json.dumps(["P1:P1_chunk_0001"]), encoding="utf-8")
    (source / "preflight_identity.json").write_text(json.dumps({"query_id": "Q1", "corpus_sha256": __import__("hashlib").sha256(corpus.read_bytes()).hexdigest(), "queries_sha256": __import__("hashlib").sha256(queries.read_bytes()).hexdigest()}), encoding="utf-8")
    original_sha = __import__("hashlib").sha256(raw_path.read_bytes()).hexdigest()
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    replay = replay_qa_v11(source, corpus, queries, tmp_path / "replay")
    assert replay["results"][0].execution_status == "success"
    assert __import__("hashlib").sha256(raw_path.read_bytes()).hexdigest() == original_sha
    assert (tmp_path / "replay" / "replay_manifest.json").is_file()


def _inputs(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"passage_id": "P1:P1_chunk_0001", "paper_key": "P1", "citation_key": "cite", "title": "title", "year": 2024, "chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "text": "alpha evidence", "text_sha256": "x", "source_context_sha256": "y"}) + "\n", encoding="utf-8")
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps({"metadata": {}, "queries": [{"query_id": "Q1", "query_zh": "alpha", "query_en": "alpha", "query_type": "method", "expected_answerable": True, "relevant_paper_keys": ["P1"], "relevant_passage_ids": ["P1:P1_chunk_0001"], "gold_evidence_summary": "secret", "review_status": "human_reviewed_pilot"}, {"query_id": "Q2", "query_zh": "unknown", "query_en": "unknown", "query_type": "no_answer", "expected_answerable": False, "relevant_paper_keys": [], "relevant_passage_ids": [], "gold_evidence_summary": "secret", "review_status": "human_reviewed_pilot"}]}), encoding="utf-8")
    return corpus, queries
