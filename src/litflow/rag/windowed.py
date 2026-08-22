from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from litflow.rag.bm25 import BM25Index, RagValidationError, _metrics, _percentile, _sha256_file, _tokenize, _top10_misses, load_corpus
from litflow.rag.dense import MAX_LENGTH, MODEL_NAME, MODEL_REVISION, NORMALIZATION, PASSAGE_PREFIX, POOLING, QUERY_PREFIX, _Encoder
from litflow.rag.qrels import load_queries, qrels_evaluation_label


WINDOW_OVERLAP_TOKENS = 64


def build_windowed_dense_cache(corpus_path: Path, cache_dir: Path, *, model_name: str = MODEL_NAME, revision: str = MODEL_REVISION) -> dict[str, Any]:
    passages = load_corpus(corpus_path)
    if cache_dir.exists() and any(cache_dir.iterdir()):
        raise RagValidationError("windowed dense cache already exists")
    started = time.perf_counter()
    encoder = _Encoder(model_name, revision)
    special = encoder.tokenizer.num_special_tokens_to_add(pair=False)
    prefix_ids = encoder.tokenizer(PASSAGE_PREFIX, add_special_tokens=False)["input_ids"]
    budget = MAX_LENGTH - special - len(prefix_ids)
    if budget <= WINDOW_OVERLAP_TOKENS:
        raise RagValidationError("window budget must exceed overlap")
    rows = []
    texts = []
    for passage in passages:
        ids = encoder.tokenizer(passage["text"], add_special_tokens=False)["input_ids"]
        for index, (start, end) in enumerate(_window_ranges(len(ids), budget, WINDOW_OVERLAP_TOKENS), 1):
            text = encoder.tokenizer.decode(ids[start:end], skip_special_tokens=True, clean_up_tokenization_spaces=False)
            while len(encoder.tokenizer(PASSAGE_PREFIX + text, add_special_tokens=True)["input_ids"]) > MAX_LENGTH:
                ids = ids[start:end - 1]
                text = encoder.tokenizer.decode(ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)
                end -= 1
            rows.append({"window_id": f"{passage['passage_id']}:w{index:04d}", "parent_passage_id": passage["passage_id"], "token_start": start, "token_end": end})
            texts.append(PASSAGE_PREFIX + text)
    embeddings = encoder.encode(texts)
    cache_dir.mkdir(parents=True)
    np.save(cache_dir / "window_embeddings.npy", embeddings)
    (cache_dir / "windows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"corpus_sha256": _sha256_file(corpus_path), "model_name": model_name, "model_revision": revision, "pooling": POOLING, "normalization": NORMALIZATION, "query_prefix": QUERY_PREFIX, "passage_prefix": PASSAGE_PREFIX, "max_length": MAX_LENGTH, "window_content_token_budget": budget, "window_overlap_tokens": WINDOW_OVERLAP_TOKENS, "parent_aggregation": "max", "parent_passage_count": len(passages), "window_count": len(rows), "embedding_dimension": int(embeddings.shape[1]), "cache_bytes": (cache_dir / "window_embeddings.npy").stat().st_size, "build_time_ms": round((time.perf_counter() - started) * 1000, 6), "device": encoder.device}
    (cache_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


class WindowedDenseIndex:
    def __init__(self, corpus_path: Path, cache_dir: Path) -> None:
        self.passages = load_corpus(corpus_path)
        self.manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest["corpus_sha256"] != _sha256_file(corpus_path):
            raise RagValidationError("windowed cache corpus identity mismatch")
        self.windows = json.loads((cache_dir / "windows.json").read_text(encoding="utf-8"))
        self.embeddings = np.load(cache_dir / "window_embeddings.npy")
        if len(self.windows) != len(self.embeddings):
            raise RagValidationError("windowed cache embedding identity mismatch")
        self.encoder = _Encoder(self.manifest["model_name"], self.manifest["model_revision"])

    def search(self, query: str, *, top_k: int = 10) -> list[dict[str, Any]]:
        if not _tokenize(query):
            return []
        scores = self.embeddings @ self.encoder.encode([QUERY_PREFIX + query])[0]
        parent_scores: dict[str, float] = {}
        for score, row in zip(scores, self.windows):
            parent = row["parent_passage_id"]
            parent_scores[parent] = max(parent_scores.get(parent, float("-inf")), float(score))
        ordered = sorted(parent_scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        return [{"passage_id": passage_id, "score": round(score, 12), "rank": index} for index, (passage_id, score) in enumerate(ordered, 1)]


def evaluate_windowed(corpus_path: Path, queries_path: Path, cache_dir: Path, out_dir: Path, *, mode: str) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RagValidationError("evaluation output directory already exists and is nonempty")
    if mode not in {"dense_zh_windowed", "hybrid_zh_windowed"}:
        raise RagValidationError("unknown windowed mode")
    passages, queries = load_corpus(corpus_path), load_queries(queries_path)
    index = WindowedDenseIndex(corpus_path, cache_dir)
    bm25 = BM25Index(passages) if mode == "hybrid_zh_windowed" else None
    records, latencies = [], []
    for position, query in enumerate(queries):
        started = time.perf_counter()
        dense = index.search(query["query_zh"])
        results = _rrf([bm25.search(query["query_zh"]), dense]) if bm25 else dense
        latency = (time.perf_counter() - started) * 1000
        latencies.append(latency)
        records.append({"query_id": query["query_id"], "expected_answerable": query["expected_answerable"], "results": results, "latency_ms": round(latency, 6), "cold": position == 0})
    answerable = [query for query in queries if query["expected_answerable"]]
    report = {"label": qrels_evaluation_label(queries_path), "mode": mode, "corpus_sha256": _sha256_file(corpus_path), "queries_sha256": _sha256_file(queries_path), "metrics": _metrics(records, answerable), "answerable_query_count": len(answerable), "no_answer_query_count": len(queries) - len(answerable), "latency_ms": {"cold_query": round(latencies[0], 6), "warm_p50": _percentile(latencies[1:], .5), "warm_p95": _percentile(latencies[1:], .95)}, "window_cache": index.manifest, "failure_cases": _top10_misses(records, answerable)}
    out_dir.mkdir(parents=True)
    (out_dir / f"per_query_{mode}.jsonl").write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    (out_dir / f"metrics_{mode}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _window_ranges(length: int, budget: int, overlap: int) -> list[tuple[int, int]]:
    if length == 0:
        return [(0, 0)]
    step = budget - overlap
    result = []
    start = 0
    while start < length:
        end = min(length, start + budget)
        result.append((start, end))
        if end == length:
            break
        start += step
    return result


def _rrf(rankings: list[list[dict[str, Any]]], *, k: int = 60, top_k: int = 10) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for item in ranking:
            scores[item["passage_id"]] = scores.get(item["passage_id"], 0.0) + 1 / (k + item["rank"])
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
    return [{"passage_id": passage_id, "score": round(score, 12), "rank": index} for index, (passage_id, score) in enumerate(ordered, 1)]
