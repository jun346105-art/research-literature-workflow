from __future__ import annotations

import json

import pytest

from litflow.evidence_writing import WritingValidationError, validate_author_closure, validate_writing_output


def test_writing_validator_rejects_unknown_record_and_single_paper_synthesis():
    records = [_record("ER1", "P1", "cite1"), _record("ER2", "P2", "cite2")]
    output = _output(["MISSING"], ["cite1"], "evidence_claim")
    with pytest.raises(WritingValidationError, match="unknown evidence record"):
        validate_writing_output(output, "T1", records)
    output = _output(["ER1"], ["cite1"], "cross_paper_synthesis")
    with pytest.raises(WritingValidationError, match="two distinct papers"):
        validate_writing_output(output, "T1", records)


def test_writing_validator_accepts_bilingual_bound_sentences_and_partial_limitations():
    records = [_record("ER1", "P1", "cite1"), _record("ER2", "P2", "cite2", partial=True)]
    output = _output(["ER1", "ER2"], ["cite1", "cite2"], "cross_paper_synthesis")
    validated = validate_writing_output(output, "T1", records)
    assert validated["sentences"][0]["sentence_id"] == "S1"
    assert "TPMN" in validated["limitations_zh"]


def test_author_closure_rejects_unknown_or_failed_records():
    records = [_record("ER1", "P1", "cite1"), {**_record("ER2", "P2", "cite2"), "review_decision": "fail"}]
    sentence = {"sentence_id": "S1", "text_zh": "修订", "text_en": "Revision", "supporting_record_ids": ["MISSING"], "citation_keys": []}
    with pytest.raises(WritingValidationError, match="unknown evidence record"):
        validate_author_closure([sentence], records)
    sentence["supporting_record_ids"] = ["ER2"]
    sentence["citation_keys"] = ["cite2"]
    with pytest.raises(WritingValidationError, match="failed evidence record"):
        validate_author_closure([sentence], records)


def _record(record_id, paper_key, citation_key, partial=False):
    return {"evidence_record_id": record_id, "paper_key": paper_key, "citation_key": citation_key, "claim_text": "claim", "review_decision": "pass", "coverage_status": "partial" if partial else "complete", "limitations": ["当前证据未覆盖：TPMN"] if partial else [], "citations": [{"page_start": 1, "page_end": 1, "evidence_quote": "quote"}]}


def _output(record_ids, citation_keys, sentence_type):
    return {"task_id": "T1", "section_type": "method_comparison", "outline": [{"outline_id": "O1", "heading_zh": "方法比较", "heading_en": "Method comparison", "purpose_zh": "比较", "supporting_record_ids": record_ids}], "sentences": [{"sentence_id": "S1", "sentence_type": sentence_type, "text_zh": "中文句子", "text_en": "English sentence", "supporting_record_ids": record_ids, "citation_keys": citation_keys}], "limitations_zh": "当前证据未覆盖：TPMN", "limitations_en": "Current evidence does not cover TPMN."}
