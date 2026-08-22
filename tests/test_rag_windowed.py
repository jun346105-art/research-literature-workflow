from __future__ import annotations

import json

import numpy as np

from litflow.rag.windowed import WindowedDenseIndex, _window_ranges


class FakeEncoder:
    def __init__(self, *_args):
        self.device = "cpu"

    def encode(self, texts, **_kwargs):
        return np.array([[1.0, 0.0] for _ in texts], dtype="float32")


def test_window_ranges_respect_budget_and_overlap():
    ranges = _window_ranges(1200, 500, 64)
    assert all(end - start <= 500 for start, end in ranges)
    assert all(right[0] == left[1] - 64 for left, right in zip(ranges, ranges[1:]))
    assert ranges[-1][1] == 1200


def test_windowed_parent_max_and_deterministic_parent_ids(tmp_path, monkeypatch):
    monkeypatch.setattr("litflow.rag.windowed._Encoder", FakeEncoder)
    corpus = tmp_path / "corpus.jsonl"
    passages = [_passage("P1:P1_chunk_0001"), _passage("P2:P2_chunk_0001")]
    corpus.write_text("".join(json.dumps(row) + "\n" for row in passages), encoding="utf-8")
    cache = tmp_path / "cache"; cache.mkdir()
    (cache / "manifest.json").write_text(json.dumps({"corpus_sha256": __import__("hashlib").sha256(corpus.read_bytes()).hexdigest(), "model_name": "m", "model_revision": "r", "embedding_dimension": 2}), encoding="utf-8")
    (cache / "windows.json").write_text(json.dumps([{"window_id": "w1", "parent_passage_id": "P1:P1_chunk_0001", "token_start": 0, "token_end": 2}, {"window_id": "w2", "parent_passage_id": "P1:P1_chunk_0001", "token_start": 2, "token_end": 4}, {"window_id": "w3", "parent_passage_id": "P2:P2_chunk_0001", "token_start": 0, "token_end": 2}]), encoding="utf-8")
    np.save(cache / "window_embeddings.npy", np.array([[0.2, 0.0], [0.9, 0.0], [0.8, 0.0]], dtype="float32"))
    index = WindowedDenseIndex(corpus, cache)
    assert [item["passage_id"] for item in index.search("query")] == ["P1:P1_chunk_0001", "P2:P2_chunk_0001"]


def _passage(passage_id: str) -> dict:
    paper, chunk = passage_id.split(":")
    return {"passage_id": passage_id, "paper_key": paper, "citation_key": "cite", "title": "title", "year": 2024, "chunk_id": chunk, "page_start": 1, "page_end": 1, "text": "text", "text_sha256": "text", "source_context_sha256": "context"}
