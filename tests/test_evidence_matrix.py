from __future__ import annotations

import json

from litflow.evidence_matrix import build_evidence_matrix


def test_matrix_uses_human_correction_and_excludes_failed_or_unreviewed(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps(_passage()) + "\n", encoding="utf-8")
    results = tmp_path / "results.json"
    results.write_text(json.dumps([
        {"query_id": "Q1", "execution_status": "success", "final_answer_status": "answered", "coverage_status": "complete", "claims": [{"subject_paper_key": "P1", "claim_text_zh": "model claim", "citations": [{"passage_id": "P1:C1", "page_start": 1, "page_end": 1, "evidence_quote": "source quote", "anchor_status": "exact_match"}]}]},
        {"query_id": "Q2", "execution_status": "quote_grounding_failed", "claims": []},
    ]), encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"valid_answer_reviews": {"Q1": {"author_decision": "pass_with_minor_revision", "human_reviewed_correction": "human correction"}}}), encoding="utf-8")
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps({"queries": [{"query_id": "Q1", "query_type": "method"}, {"query_id": "Q2", "query_type": "method"}]}), encoding="utf-8")
    output = tmp_path / "out"
    report = build_evidence_matrix(results, review, corpus, queries, output, input_identity={"corpus_sha256": "x"})
    records = [json.loads(line) for line in (output / "evidence_records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["claim_text"] == "human correction"
    assert records[0]["original_model_claim"] == "model claim"
    assert report["record_count"] == 1


def test_matrix_preserves_partial_uncovered_entity_and_quote_provenance(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps(_passage()) + "\n", encoding="utf-8")
    results = tmp_path / "results.json"
    results.write_text(json.dumps([{"query_id": "Q15", "execution_status": "success", "final_answer_status": "partial_answer", "coverage_status": "partial", "coverage_ledger": {"uncovered_entities": [{"entity_name": "TPMN"}]}, "claims": [{"subject_paper_key": "P1", "claim_text_zh": "covered claim", "citations": [{"passage_id": "P1:C1", "page_start": 1, "page_end": 1, "evidence_quote": "source quote", "anchor_status": "exact_match"}]}]}]), encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"valid_answer_reviews": {"Q15": {"author_decision": "pass"}}}), encoding="utf-8")
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps({"queries": [{"query_id": "Q15", "query_type": "cross_paper"}]}), encoding="utf-8")
    output = tmp_path / "out"
    build_evidence_matrix(results, review, corpus, queries, output, input_identity={})
    record = json.loads((output / "evidence_records.jsonl").read_text(encoding="utf-8"))
    assert record["coverage_status"] == "partial"
    assert any("TPMN" in item for item in record["limitations"])
    assert record["citations"][0]["evidence_quote"] == "source quote"


def _passage():
    return {"passage_id": "P1:C1", "paper_key": "P1", "citation_key": "cite", "title": "Paper", "year": 2025, "source_language": "en", "page_start": 1, "page_end": 1, "text": "source quote", "text_sha256": "text-sha", "source_context_sha256": "context-sha"}
