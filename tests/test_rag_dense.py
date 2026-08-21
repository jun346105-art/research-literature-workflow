from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from litflow.rag.bm25 import RagValidationError
from litflow.rag.dense import DenseIndex, build_dense_cache, evaluate_retriever, rrf_fuse


class FakeEncoder:
    def __init__(self, *_args):
        self.device = "cpu"

    def encode(self, texts, **_kwargs):
        rows = []
        for text in texts:
            rows.append([1.0, 0.0] if "alpha" in text.lower() else [0.0, 1.0])
        return np.array(rows, dtype="float32")


def test_dense_cache_identity_and_stable_tie_breaking(tmp_path, monkeypatch):
    monkeypatch.setattr("litflow.rag.dense._Encoder", FakeEncoder)
    corpus = _corpus(tmp_path)
    cache = tmp_path / "cache"
    manifest = build_dense_cache(corpus, cache)
    assert manifest["embedding_dimension"] == 2
    assert manifest["query_prefix"] == "query: "
    assert manifest["passage_prefix"] == "passage: "
    index = DenseIndex(corpus, cache)
    assert [item["passage_id"] for item in index.search("alpha")] == ["P1:P1_chunk_0001", "P2:P2_chunk_0001"]


def test_rrf_deduplicates_and_breaks_ties_by_passage_id():
    fused = rrf_fuse([[{"passage_id": "b", "rank": 1}, {"passage_id": "a", "rank": 1}], [{"passage_id": "a", "rank": 1}, {"passage_id": "b", "rank": 1}]])
    assert [item["passage_id"] for item in fused] == ["a", "b"]


def test_dense_eval_marks_silver_and_separates_no_answer(tmp_path, monkeypatch):
    monkeypatch.setattr("litflow.rag.dense._Encoder", FakeEncoder)
    corpus = _corpus(tmp_path)
    cache = tmp_path / "cache"
    build_dense_cache(corpus, cache)
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps({"queries": [
        {"query_id": "q1", "query_en": "alpha", "query_zh": "alpha", "query_type": "method", "expected_answerable": True, "relevant_paper_keys": ["P1"], "relevant_passage_ids": ["P1:P1_chunk_0001"], "gold_evidence_summary": "", "review_status": "human_review_pending"},
        {"query_id": "q2", "query_en": "unknown", "query_zh": "unknown", "query_type": "no_answer", "expected_answerable": False, "relevant_paper_keys": [], "relevant_passage_ids": [], "gold_evidence_summary": "", "review_status": "human_review_pending"},
    ]}), encoding="utf-8")
    report = evaluate_retriever(corpus, queries, tmp_path / "eval", mode="dense_en", cache_dir=cache)
    assert report["label"] == "preliminary_on_AI_drafted_silver_qrels"
    assert report["answerable_query_count"] == 1
    assert report["no_answer_query_count"] == 1
    assert report["metrics"]["hit_at_1"] == 1.0


def test_dense_cache_rejects_corpus_identity_change(tmp_path, monkeypatch):
    monkeypatch.setattr("litflow.rag.dense._Encoder", FakeEncoder)
    corpus = _corpus(tmp_path)
    cache = tmp_path / "cache"
    build_dense_cache(corpus, cache)
    corpus.write_text(corpus.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RagValidationError, match="identity mismatch"):
        DenseIndex(corpus, cache)


def _corpus(tmp_path: Path) -> Path:
    path = tmp_path / "corpus.jsonl"
    rows = []
    for passage_id, text in [("P1:P1_chunk_0001", "alpha passage"), ("P2:P2_chunk_0001", "alpha passage")]:
        paper, chunk = passage_id.split(":")
        rows.append({"passage_id": passage_id, "paper_key": paper, "citation_key": "cite", "title": "title", "year": 2024, "chunk_id": chunk, "page_start": 1, "page_end": 1, "text": text, "text_sha256": "text", "source_context_sha256": "context"})
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path
