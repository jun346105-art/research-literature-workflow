from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from litflow.rag.qrels import load_queries


class RagValidationError(ValueError):
    pass


def build_corpus(frozen_manifest_path: Path, corpus_path: Path, manifest_path: Path) -> dict[str, Any]:
    frozen = _load_json(frozen_manifest_path)
    if corpus_path.exists() or manifest_path.exists():
        raise RagValidationError("corpus outputs already exist")
    papers = frozen.get("papers")
    if not isinstance(papers, list) or not papers:
        raise RagValidationError("frozen corpus manifest contains no papers")
    rows = []
    seen = set()
    for paper in papers:
        context_path = Path(paper["source_clean_context_path"])
        if not context_path.is_absolute():
            context_path = frozen_manifest_path.parents[3] / context_path
        if not context_path.is_file() or _sha256_file(context_path) != paper.get("clean_context_sha256"):
            raise RagValidationError(f"clean context SHA-256 mismatch: {paper.get('paper_key')}")
        context = _load_json(context_path)
        for chunk in context.get("chunks", []):
            passage_id = f"{paper['paper_key']}:{chunk['chunk_id']}"
            if passage_id in seen:
                raise RagValidationError(f"duplicate passage id: {passage_id}")
            seen.add(passage_id)
            text = chunk.get("text") or ""
            rows.append({"passage_id": passage_id, "paper_key": paper["paper_key"], "citation_key": paper.get("citation_key"), "title": paper.get("title"), "year": paper.get("year"), "chunk_id": chunk["chunk_id"], "page_start": chunk["page_start"], "page_end": chunk["page_end"], "text": text, "text_sha256": _sha256_text(text), "source_context_sha256": paper["clean_context_sha256"]})
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    report = {"corpus_id": frozen.get("metadata", {}).get("corpus_id", "unknown"), "paper_count": len(papers), "passage_count": len(rows), "frozen_manifest_sha256": _sha256_file(frozen_manifest_path), "corpus_sha256": _sha256_file(corpus_path), "tokenizer": "lowercase_alnum_plus_cjk_chars_v1"}
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


class BM25Index:
    def __init__(self, passages: list[dict[str, Any]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.passages, self.k1, self.b = passages, k1, b
        self.tokens = [_tokenize(item["text"]) for item in passages]
        self.lengths = [len(item) for item in self.tokens]
        self.avgdl = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        self.document_frequency = Counter(token for tokens in self.tokens for token in set(tokens))

    def search(self, query: str, *, top_k: int = 10) -> list[dict[str, Any]]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        total = len(self.passages)
        scores = []
        for passage, tokens, length in zip(self.passages, self.tokens, self.lengths):
            term_frequency = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                df = self.document_frequency.get(token, 0)
                if not df or token not in term_frequency:
                    continue
                idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
                score += idf * term_frequency[token] * (self.k1 + 1) / (term_frequency[token] + self.k1 * (1 - self.b + self.b * length / self.avgdl))
            if score > 0:
                scores.append({"passage_id": passage["passage_id"], "score": round(score, 12), "rank": 0})
        scores.sort(key=lambda item: (-item["score"], item["passage_id"]))
        return [{**item, "rank": index} for index, item in enumerate(scores[:top_k], 1)]


def load_corpus(corpus_path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    ids = [row.get("passage_id") for row in rows]
    if not rows or len(ids) != len(set(ids)):
        raise RagValidationError("corpus is empty or contains duplicate passage IDs")
    return rows


def evaluate_bm25(corpus_path: Path, queries_path: Path, out_dir: Path, *, mode: str) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise RagValidationError("evaluation output directory already exists and is nonempty")
    if mode not in {"en", "zh_raw"}:
        raise RagValidationError("mode must be en or zh_raw")
    passages = load_corpus(corpus_path)
    queries = load_queries(queries_path)
    known_ids = {row["passage_id"] for row in passages}
    for query in queries:
        unknown = set(query.get("relevant_passage_ids", [])) - known_ids
        if unknown:
            raise RagValidationError(f"qrels reference unknown passage IDs: {sorted(unknown)}")
    index = BM25Index(passages)
    started = time.perf_counter()
    records = []
    latencies = []
    for query in queries:
        text = query["query_en"] if mode == "en" else query["query_zh"]
        query_started = time.perf_counter()
        results = index.search(text, top_k=10)
        latency = (time.perf_counter() - query_started) * 1000
        latencies.append(latency)
        records.append({"query_id": query["query_id"], "expected_answerable": query["expected_answerable"], "results": results, "latency_ms": round(latency, 6)})
    answerable = [query for query in queries if query["expected_answerable"]]
    metrics = _metrics(records, answerable)
    report = {"label": "preliminary_on_AI_drafted_silver_qrels", "mode": mode, "corpus_sha256": _sha256_file(corpus_path), "queries_sha256": _sha256_file(queries_path), "query_count": len(queries), "answerable_query_count": len(answerable), "no_answer_query_count": len(queries) - len(answerable), "metrics": metrics, "latency_ms": {"p50": _percentile(latencies, .5), "p95": _percentile(latencies, .95), "total": round((time.perf_counter() - started) * 1000, 6)}, "failure_cases": _top10_misses(records, answerable)}
    out_dir.mkdir(parents=True)
    (out_dir / f"per_query_{mode}.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")
    (out_dir / f"metrics_{mode}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _metrics(records: list[dict[str, Any]], answerable: list[dict[str, Any]]) -> dict[str, float | None]:
    by_id = {item["query_id"]: item for item in records}
    if not answerable:
        return {"hit_at_1": None, "recall_at_5": None, "recall_at_10": None, "mrr_at_10": None, "ndcg_at_10": None}
    values = {"hit_at_1": [], "recall_at_5": [], "recall_at_10": [], "mrr_at_10": [], "ndcg_at_10": []}
    for query in answerable:
        relevant = set(query.get("relevant_passage_ids", []))
        ranked = [item["passage_id"] for item in by_id[query["query_id"]]["results"]]
        values["hit_at_1"].append(float(bool(ranked and ranked[0] in relevant)))
        for name, k in (("recall_at_5", 5), ("recall_at_10", 10)):
            values[name].append(len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0)
        first = next((index for index, passage in enumerate(ranked[:10], 1) if passage in relevant), None)
        values["mrr_at_10"].append(1 / first if first else 0.0)
        dcg = sum(1 / math.log2(index + 1) for index, passage in enumerate(ranked[:10], 1) if passage in relevant)
        ideal = sum(1 / math.log2(index + 1) for index in range(1, min(len(relevant), 10) + 1))
        values["ndcg_at_10"].append(dcg / ideal if ideal else 0.0)
    return {name: round(sum(items) / len(items), 6) for name, items in values.items()}


def _top10_misses(records: list[dict[str, Any]], answerable: list[dict[str, Any]]) -> list[str]:
    by_id = {item["query_id"]: item for item in records}
    return [query["query_id"] for query in answerable if not (set(item["passage_id"] for item in by_id[query["query_id"]]["results"][:10]) & set(query.get("relevant_passage_ids", [])))]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.casefold())


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    return round(sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)], 6)
