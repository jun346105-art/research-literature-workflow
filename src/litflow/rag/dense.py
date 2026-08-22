from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from litflow.rag.bm25 import BM25Index, RagValidationError, _metrics, _percentile, _sha256_file, _tokenize, _top10_misses, load_corpus
from litflow.rag.qrels import load_queries, qrels_evaluation_label


MODEL_NAME = "intfloat/multilingual-e5-small"
MODEL_REVISION = "053834db62d809d8f124a76b687fbd948e13ef3e"
POOLING = "attention_mask_mean"
NORMALIZATION = "l2"
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "
MAX_LENGTH = 512


def build_dense_cache(corpus_path: Path, cache_dir: Path, *, model_name: str = MODEL_NAME, revision: str = MODEL_REVISION) -> dict[str, Any]:
    passages = load_corpus(corpus_path)
    identity = _identity(corpus_path, model_name, revision)
    manifest_path = cache_dir / "manifest.json"
    embedding_path = cache_dir / "passage_embeddings.npy"
    ids_path = cache_dir / "passage_ids.json"
    if manifest_path.exists() or embedding_path.exists() or ids_path.exists():
        raise RagValidationError("dense cache already exists")
    started = time.perf_counter()
    encoder = _Encoder(model_name, revision)
    embeddings = encoder.encode([PASSAGE_PREFIX + passage["text"] for passage in passages])
    cache_dir.mkdir(parents=True)
    np.save(embedding_path, embeddings)
    ids_path.write_text(json.dumps([passage["passage_id"] for passage in passages]) + "\n", encoding="utf-8")
    manifest = {**identity, "embedding_dimension": int(embeddings.shape[1]), "passage_count": len(passages), "build_time_ms": round((time.perf_counter() - started) * 1000, 6), "embedding_cache_bytes": embedding_path.stat().st_size, "device": encoder.device}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


class DenseIndex:
    def __init__(self, corpus_path: Path, cache_dir: Path) -> None:
        self.passages = load_corpus(corpus_path)
        self.manifest = _load(cache_dir / "manifest.json")
        if self.manifest != {**_identity(corpus_path, self.manifest["model_name"], self.manifest["model_revision"]), **{key: self.manifest[key] for key in ("embedding_dimension", "passage_count", "build_time_ms", "embedding_cache_bytes", "device")}}:
            raise RagValidationError("dense cache identity mismatch")
        self.embeddings = np.load(cache_dir / "passage_embeddings.npy")
        self.ids = json.loads((cache_dir / "passage_ids.json").read_text(encoding="utf-8"))
        if self.embeddings.shape != (len(self.passages), self.manifest["embedding_dimension"]) or self.ids != [item["passage_id"] for item in self.passages]:
            raise RagValidationError("dense cache passage identity mismatch")
        self.encoder = _Encoder(self.manifest["model_name"], self.manifest["model_revision"])

    def search(self, query: str, *, top_k: int = 10) -> list[dict[str, Any]]:
        if not _tokenize(query):
            return []
        query_embedding = self.encoder.encode([QUERY_PREFIX + query])[0]
        scores = self.embeddings @ query_embedding
        ordered = sorted(((float(score), passage_id) for score, passage_id in zip(scores, self.ids)), key=lambda item: (-item[0], item[1]))[:top_k]
        return [{"passage_id": passage_id, "score": round(score, 12), "rank": index} for index, (score, passage_id) in enumerate(ordered, 1)]


def rrf_fuse(rankings: list[list[dict[str, Any]]], *, k: int = 60, top_k: int = 10) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        seen = set()
        for item in ranking:
            passage_id, rank = item["passage_id"], item["rank"]
            if passage_id in seen:
                continue
            seen.add(passage_id)
            scores[passage_id] = scores.get(passage_id, 0.0) + 1 / (k + rank)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
    return [{"passage_id": passage_id, "score": round(score, 12), "rank": index} for index, (passage_id, score) in enumerate(ordered, 1)]


def evaluate_retriever(corpus_path: Path, queries_path: Path, out_dir: Path, *, mode: str, cache_dir: Path | None = None) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RagValidationError("evaluation output directory already exists and is nonempty")
    passages, queries = load_corpus(corpus_path), load_queries(queries_path)
    _validate_qrels(queries, passages)
    dense = DenseIndex(corpus_path, cache_dir) if cache_dir else None
    bm25 = BM25Index(passages) if mode.startswith("hybrid") else None
    records, latencies = [], []
    for index, query in enumerate(queries):
        started = time.perf_counter()
        en, zh = query["query_en"], query["query_zh"]
        if mode == "dense_en": results = dense.search(en)
        elif mode == "dense_zh": results = dense.search(zh)
        elif mode == "hybrid_zh": results = rrf_fuse([bm25.search(zh), dense.search(zh)])
        elif mode == "hybrid_bilingual": results = rrf_fuse([bm25.search(en), dense.search(zh)])
        else: raise RagValidationError("unknown dense/hybrid mode")
        latency = (time.perf_counter() - started) * 1000
        latencies.append(latency)
        records.append({"query_id": query["query_id"], "expected_answerable": query["expected_answerable"], "results": results, "latency_ms": round(latency, 6), "cold": index == 0})
    answerable = [query for query in queries if query["expected_answerable"]]
    report = {"label": qrels_evaluation_label(queries_path), "mode": mode, "corpus_sha256": _sha256_file(corpus_path), "queries_sha256": _sha256_file(queries_path), "metrics": _metrics(records, answerable), "answerable_query_count": len(answerable), "no_answer_query_count": len(queries) - len(answerable), "latency_ms": {"cold_query": round(latencies[0], 6), "warm_p50": _percentile(latencies[1:], .5), "warm_p95": _percentile(latencies[1:], .95)}, "embedding_cache": dense.manifest if dense else None, "failure_cases": _top10_misses(records, answerable)}
    out_dir.mkdir(parents=True)
    (out_dir / f"per_query_{mode}.jsonl").write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    (out_dir / f"metrics_{mode}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


class _Encoder:
    def __init__(self, model_name: str, revision: str) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
        self.model = AutoModel.from_pretrained(model_name, revision=revision).to(self.device).eval()

    def encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        vectors = []
        with self.torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = self.tokenizer(texts[start:start + batch_size], max_length=MAX_LENGTH, truncation=True, padding=True, return_tensors="pt")
                batch = {key: value.to(self.device) for key, value in batch.items()}
                hidden = self.model(**batch).last_hidden_state
                mask = batch["attention_mask"].unsqueeze(-1).bool()
                pooled = hidden.masked_fill(~mask, 0.0).sum(dim=1) / batch["attention_mask"].sum(dim=1, keepdim=True)
                vectors.append(self.torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().numpy().astype("float32"))
        return np.concatenate(vectors, axis=0)


def _identity(corpus_path: Path, model_name: str, revision: str) -> dict[str, Any]:
    return {"corpus_sha256": _sha256_file(corpus_path), "model_name": model_name, "model_revision": revision, "pooling": POOLING, "normalization": NORMALIZATION, "query_prefix": QUERY_PREFIX, "passage_prefix": PASSAGE_PREFIX, "max_length": MAX_LENGTH}


def _validate_qrels(queries: list[dict[str, Any]], passages: list[dict[str, Any]]) -> None:
    known = {item["passage_id"] for item in passages}
    for query in queries:
        unknown = set(query.get("relevant_passage_ids", [])) - known
        if unknown: raise RagValidationError(f"qrels reference unknown passage IDs: {sorted(unknown)}")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))
