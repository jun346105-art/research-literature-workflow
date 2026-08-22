from __future__ import annotations

import json

import pytest

from litflow.llm.client import LLMCompletion
from litflow.rag.qa import RawAnswer, SAFE_EXECUTION_FAILURE_ZH, TransportError, _parse_transport, _verify, evaluate_qa, plan_qa, replay_qa_transport, run_qa


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


def _inputs(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps({"passage_id": "P1:P1_chunk_0001", "paper_key": "P1", "citation_key": "cite", "title": "title", "year": 2024, "chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "text": "alpha evidence", "text_sha256": "x", "source_context_sha256": "y"}) + "\n", encoding="utf-8")
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps({"metadata": {}, "queries": [{"query_id": "Q1", "query_zh": "alpha", "query_en": "alpha", "query_type": "method", "expected_answerable": True, "relevant_paper_keys": ["P1"], "relevant_passage_ids": ["P1:P1_chunk_0001"], "gold_evidence_summary": "secret", "review_status": "human_reviewed_pilot"}, {"query_id": "Q2", "query_zh": "unknown", "query_en": "unknown", "query_type": "no_answer", "expected_answerable": False, "relevant_paper_keys": [], "relevant_passage_ids": [], "gold_evidence_summary": "secret", "review_status": "human_reviewed_pilot"}]}), encoding="utf-8")
    return corpus, queries
