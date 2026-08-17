from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from litflow.rag.bm25 import BM25Index, RagValidationError, build_corpus, evaluate_bm25, load_corpus


def test_build_corpus_freezes_passages_and_provenance(tmp_path):
    frozen = _frozen(tmp_path)
    corpus = tmp_path / "passages.jsonl"
    manifest = tmp_path / "corpus_manifest.json"
    report = build_corpus(frozen, corpus, manifest)
    rows = load_corpus(corpus)

    assert report["passage_count"] == 2
    assert rows[0]["passage_id"] == "P1:P1_chunk_0001"
    assert rows[0]["text_sha256"] == hashlib.sha256(rows[0]["text"].encode("utf-8")).hexdigest()
    assert rows[0]["page_start"] == 1
    assert rows[0]["source_context_sha256"] == _sha(tmp_path / "P1.json")


def test_duplicate_passage_and_empty_query_are_safe(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    rows = [_passage("P1:P1_chunk_0001", "alpha"), _passage("P1:P1_chunk_0001", "alpha")]
    corpus.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(RagValidationError, match="duplicate"):
        load_corpus(corpus)

    index = BM25Index([_passage("P1:P1_chunk_0001", "alpha beta")])
    assert index.search("") == []


def test_bm25_deterministic_ranking_and_evaluation(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    rows = [_passage("P1:P1_chunk_0001", "alpha"), _passage("P2:P2_chunk_0001", "alpha")]
    corpus.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert [item["passage_id"] for item in BM25Index(load_corpus(corpus)).search("alpha")] == ["P1:P1_chunk_0001", "P2:P2_chunk_0001"]
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps({"queries": [
        {"query_id": "q1", "query_en": "alpha", "query_zh": "阿尔法", "query_type": "method", "expected_answerable": True, "relevant_paper_keys": ["P1"], "relevant_passage_ids": ["P1:P1_chunk_0001"], "gold_evidence_summary": "", "review_status": "human_review_pending"},
        {"query_id": "q2", "query_en": "unknown", "query_zh": "未知", "query_type": "no_answer", "expected_answerable": False, "relevant_paper_keys": [], "relevant_passage_ids": [], "gold_evidence_summary": "", "review_status": "human_review_pending"},
    ]}), encoding="utf-8")
    report = evaluate_bm25(corpus, queries, tmp_path / "eval", mode="en")
    assert report["metrics"]["hit_at_1"] == 1.0
    assert report["metrics"]["mrr_at_10"] == 1.0
    assert report["no_answer_query_count"] == 1


def test_unknown_qrels_passage_is_rejected(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps(_passage("P1:P1_chunk_0001", "alpha")) + "\n", encoding="utf-8")
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps({"queries": [{"query_id": "q", "query_en": "alpha", "query_zh": "甲", "query_type": "method", "expected_answerable": True, "relevant_paper_keys": ["P1"], "relevant_passage_ids": ["missing"], "gold_evidence_summary": "", "review_status": "human_review_pending"}]}), encoding="utf-8")
    with pytest.raises(RagValidationError, match="unknown passage"):
        evaluate_bm25(corpus, queries, tmp_path / "eval", mode="en")


def _frozen(tmp_path: Path) -> Path:
    context = tmp_path / "P1.json"
    context.write_text(json.dumps({"chunks": [{"chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "text": "alpha"}, {"chunk_id": "P1_chunk_0002", "page_start": 2, "page_end": 2, "text": "beta"}]}), encoding="utf-8")
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps({"metadata": {"corpus_id": "test"}, "papers": [{"paper_key": "P1", "citation_key": "cite", "title": "title", "year": 2024, "source_clean_context_path": str(context), "clean_context_sha256": _sha(context), "pdf_sha256": "unused", "chunk_count": 2, "quality_status": "ready_for_llm"}]}), encoding="utf-8")
    return frozen


def _passage(passage_id: str, text: str) -> dict:
    paper, chunk = passage_id.split(":")
    return {"passage_id": passage_id, "paper_key": paper, "citation_key": "cite", "title": "title", "year": 2024, "chunk_id": chunk, "page_start": 1, "page_end": 1, "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "source_context_sha256": "context"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
