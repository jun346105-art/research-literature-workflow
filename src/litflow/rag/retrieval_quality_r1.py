"""Review-gated Retrieval Quality R1 data and metric helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any


class R1EvaluationError(ValueError):
    """Raised when an R1 dataset or evaluation boundary is unsafe."""


REVIEWED_STATUS = "reviewed"
PENDING_STATUS = "pending_review"
ALLOWED_SPLITS = {"development", "dev_hard_negative", "held_out"}
TUNING_SPLITS = {"development", "dev_hard_negative"}
ALLOWED_RETRIEVER_MODES = {"bm25_zh_raw", "bm25_en", "dense_zh_windowed", "hybrid_zh_windowed"}
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")


def canonical_sha256(value: str) -> str:
    """Return the canonical lower-case form of a valid SHA-256 hex digest."""
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise R1EvaluationError("SHA-256 must be exactly 64 hexadecimal characters")
    return value.lower()


def load_r1_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("dataset_id") != "retrieval-quality-r1-v1":
        raise R1EvaluationError("unexpected R1 dataset identity")
    root = _repository_root(path)
    corpus = payload.get("corpus")
    if not isinstance(corpus, dict):
        raise R1EvaluationError("R1 corpus contract is missing")
    _verify_hash(root / corpus["path"], corpus["corpus_sha256"], "frozen corpus")
    _verify_hash(root / corpus["manifest_path"], corpus["manifest_sha256"], "frozen corpus manifest")
    passage_manifest_path = root / corpus["passage_hashes_path"]
    _verify_json_hash(passage_manifest_path, corpus["passage_hashes_sha256"], "R1 passage manifest")
    _verify_json_hash(root / payload["development_reviewed"]["path"], payload["development_reviewed"]["sha256"], "reviewed records")
    _verify_hash(root / payload["development_reviewed"]["source_path"], payload["development_reviewed"]["source_sha256"], "historical reviewed source")
    _verify_json_hash(root / payload["pending_candidates"]["path"], payload["pending_candidates"]["sha256"], "pending candidates")
    _verify_text_hash(root / payload["pending_candidates"]["review_csv"], payload["pending_candidates"]["review_csv_sha256"], "pending review CSV")
    _validate_passage_manifest(root / corpus["path"], passage_manifest_path, corpus)
    return payload


def load_r1_records(manifest_path: Path, *, split: str, allow_pending: bool = False) -> list[dict[str, Any]]:
    manifest = load_r1_manifest(manifest_path)
    if split not in ALLOWED_SPLITS:
        raise R1EvaluationError(f"unknown split: {split}")
    root = _repository_root(manifest_path)
    package_path = root / (manifest["development_reviewed"]["path"] if split == "development" else manifest["pending_candidates"]["path"])
    payload = json.loads(package_path.read_text(encoding="utf-8-sig"))
    rows = payload.get("queries")
    if not isinstance(rows, list):
        raise R1EvaluationError("R1 query package must contain a queries array")
    _validate_records(rows)
    selected = [row for row in rows if row["split"] == split]
    if not selected:
        raise R1EvaluationError(f"no records for split: {split}")
    pending = [row["query_id"] for row in selected if row["review_status"] == PENDING_STATUS]
    if pending and not allow_pending:
        raise R1EvaluationError(f"pending_review records are not eligible for formal evaluation: {pending}")
    return selected


def load_all_r1_records(manifest_path: Path, *, allow_pending: bool = False) -> list[dict[str, Any]]:
    rows = [
        *load_r1_records(manifest_path, split="development", allow_pending=allow_pending),
        *load_r1_records(manifest_path, split="dev_hard_negative", allow_pending=allow_pending),
        *load_r1_records(manifest_path, split="held_out", allow_pending=allow_pending),
    ]
    ids = [row["query_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise R1EvaluationError("query IDs overlap across R1 splits")
    return rows


def assert_tuning_split(split: str) -> None:
    if split not in TUNING_SPLITS:
        raise R1EvaluationError("held-out records cannot be used for tuning")


def validate_json_schema_documents(manifest_path: Path) -> None:
    """Validate committed R1 JSON with the optional standards validator.

    R1 does not add a runtime dependency. Formal package validation therefore
    fails closed when ``jsonschema`` is unavailable.
    """
    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError as exc:
        raise R1EvaluationError("jsonschema is required for formal R1 schema validation") from exc

    root = _repository_root(manifest_path)
    base = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    dataset_schema = json.loads((base / "schemas" / "dataset.schema.json").read_text(encoding="utf-8-sig"))
    query_schema = json.loads((base / "schemas" / "query.schema.json").read_text(encoding="utf-8-sig"))
    result_schema = json.loads((base / "schemas" / "result.schema.json").read_text(encoding="utf-8-sig"))
    for schema in (dataset_schema, query_schema, result_schema):
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise R1EvaluationError("R1 schemas must use Draft 2020-12")
        Draft202012Validator.check_schema(schema)
    _raise_schema_errors(Draft202012Validator(dataset_schema), manifest, "dataset manifest")
    for package_key in ("development_reviewed", "pending_candidates"):
        package = json.loads((root / manifest[package_key]["path"]).read_text(encoding="utf-8-sig"))
        for record in package["queries"]:
            _raise_schema_errors(Draft202012Validator(query_schema), record, record.get("query_id", "query"))
    sample_result = {"query_id": "schema-probe", "results": [], "latency_ms": 0.0}
    _raise_schema_errors(Draft202012Validator(result_schema), sample_result, "retrieval result")


def evaluate_rankings(records: list[dict[str, Any]], rankings: list[dict[str, Any]], *, retriever_mode: str) -> dict[str, Any]:
    """Evaluate supplied rankings without running or configuring a retriever.

    Recall is binary over qrel passage IDs. MRR is binary at 10. nDCG uses
    optional positive integer ``relevance_grades`` (default grade 1). For a
    no-answer record, any returned item in the first 10 is a false positive.
    """
    _validate_records(records)
    if retriever_mode not in ALLOWED_RETRIEVER_MODES:
        raise R1EvaluationError(f"unsupported R1 retriever mode: {retriever_mode}")
    if any(row["review_status"] != REVIEWED_STATUS for row in records):
        raise R1EvaluationError("formal evaluation requires reviewed records only")
    expected = {row["query_id"]: row for row in records}
    actual = {row.get("query_id"): row for row in rankings}
    if len(actual) != len(rankings) or set(expected) != set(actual):
        raise R1EvaluationError("ranking query IDs do not match evaluation records")
    values: dict[str, list[float]] = {name: [] for name in ("recall_at_5", "recall_at_10", "recall_at_20", "mrr_at_10", "ndcg_at_10")}
    latencies: list[float] = []
    answerable_count = answerable_hits_10 = answerable_hits_20 = no_answer_count = no_answer_false_positives = 0
    for query_id, record in expected.items():
        result = actual[query_id]
        ranked = _unique_passage_ids(result.get("results"))
        grades = _relevance_grades(record)
        if record["expected_answerable"]:
            answerable_count += 1
            gold = set(grades)
            answerable_hits_10 += bool(set(ranked[:10]) & gold)
            answerable_hits_20 += bool(set(ranked[:20]) & gold)
            for name, cutoff in (("recall_at_5", 5), ("recall_at_10", 10), ("recall_at_20", 20)):
                values[name].append(len(set(ranked[:cutoff]) & gold) / len(gold))
            first = next((rank for rank, passage_id in enumerate(ranked[:10], 1) if passage_id in gold), None)
            values["mrr_at_10"].append(1 / first if first else 0.0)
            dcg = sum((2 ** grades[passage_id] - 1) / math.log2(rank + 1) for rank, passage_id in enumerate(ranked[:10], 1) if passage_id in grades)
            ideal = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(sorted(grades.values(), reverse=True)[:10], 1))
            values["ndcg_at_10"].append(dcg / ideal if ideal else 0.0)
        else:
            no_answer_count += 1
            no_answer_false_positives += bool(ranked[:10])
        latency = result.get("latency_ms")
        if latency is not None:
            latency = float(latency)
            if latency < 0:
                raise R1EvaluationError("latency_ms must be non-negative")
            latencies.append(latency)
    success_10 = answerable_hits_10 / answerable_count if answerable_count else None
    return {
        "retriever_mode": retriever_mode,
        "query_count": len(records),
        "answerable_query_count": answerable_count,
        "no_answer_query_count": no_answer_count,
        "metrics": {name: round(statistics.fmean(items), 6) if items else None for name, items in values.items()},
        "answerable_retrieval_success_at_10": success_10,
        "answerable_retrieval_success_at_20": answerable_hits_20 / answerable_count if answerable_count else None,
        "answerable_success_at_10": success_10,
        "no_answer_false_positive_rate_at_10": no_answer_false_positives / no_answer_count if no_answer_count else None,
        "latency_ms": {"mean": _mean(latencies), "p50": _percentile(latencies, 0.5), "p95": _percentile(latencies, 0.95), "count": len(latencies)},
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_hash(path: Path, expected: str, label: str) -> None:
    if canonical_sha256(expected) != canonical_sha256(sha256_file(path)):
        raise R1EvaluationError(f"{label} SHA-256 mismatch")


def _verify_json_hash(path: Path, expected: str, label: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    actual = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if canonical_sha256(expected) != actual:
        raise R1EvaluationError(f"{label} SHA-256 mismatch")


def _verify_text_hash(path: Path, expected: str, label: str) -> None:
    normalized = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    actual = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if canonical_sha256(expected) != actual:
        raise R1EvaluationError(f"{label} SHA-256 mismatch")


def _validate_passage_manifest(corpus_path: Path, passage_manifest_path: Path, corpus: dict[str, Any]) -> None:
    corpus_rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    frozen = json.loads(passage_manifest_path.read_text(encoding="utf-8-sig"))
    if frozen.get("passage_count") != corpus.get("passage_count") or len(corpus_rows) != corpus.get("passage_count"):
        raise R1EvaluationError("frozen passage count mismatch")
    by_id = {row["passage_id"]: row for row in corpus_rows}
    frozen_rows = frozen.get("passages")
    if not isinstance(frozen_rows, list) or len(by_id) != len(corpus_rows) or len(frozen_rows) != len(corpus_rows):
        raise R1EvaluationError("frozen passage identities are not unique")
    for row in frozen_rows:
        actual = by_id.get(row.get("passage_id"))
        if actual is None or row.get("paper_key") != actual.get("paper_key"):
            raise R1EvaluationError("frozen passage source identity mismatch")
        for key in ("text_sha256", "source_context_sha256"):
            if canonical_sha256(row.get(key)) != canonical_sha256(actual.get(key)):
                raise R1EvaluationError(f"frozen passage {key} mismatch")


def _validate_records(records: list[dict[str, Any]]) -> None:
    ids: list[str] = []
    for row in records:
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or row.get("split") not in ALLOWED_SPLITS:
            raise R1EvaluationError("invalid query identity or split")
        if row.get("review_status") not in {REVIEWED_STATUS, PENDING_STATUS}:
            raise R1EvaluationError(f"invalid review status: {query_id}")
        passage_ids = row.get("relevant_passage_ids")
        paper_keys = row.get("relevant_paper_keys")
        if not isinstance(passage_ids, list) or not isinstance(paper_keys, list):
            raise R1EvaluationError(f"invalid qrels: {query_id}")
        if len(passage_ids) != len(set(passage_ids)) or len(paper_keys) != len(set(paper_keys)):
            raise R1EvaluationError(f"duplicate qrels: {query_id}")
        if bool(row.get("expected_answerable")) != bool(passage_ids):
            raise R1EvaluationError(f"answerability and qrels disagree: {query_id}")
        if not row.get("expected_answerable") and paper_keys:
            raise R1EvaluationError(f"no-answer record contains positive source qrels: {query_id}")
        grades = row.get("relevance_grades")
        if grades is not None and (not isinstance(grades, dict) or set(grades) != set(passage_ids) or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in grades.values())):
            raise R1EvaluationError(f"invalid graded relevance: {query_id}")
        ids.append(query_id)
    if len(ids) != len(set(ids)):
        raise R1EvaluationError("duplicate query_id")


def _relevance_grades(record: dict[str, Any]) -> dict[str, int]:
    configured = record.get("relevance_grades")
    return dict(configured) if configured is not None else {passage_id: 1 for passage_id in record["relevant_passage_ids"]}


def _unique_passage_ids(results: Any) -> list[str]:
    if not isinstance(results, list):
        raise R1EvaluationError("ranking results must be an array")
    seen: set[str] = set()
    ranked: list[str] = []
    for item in results:
        if not isinstance(item, dict) or not isinstance(item.get("passage_id"), str):
            raise R1EvaluationError("ranking item must contain passage_id")
        if item["passage_id"] not in seen:
            seen.add(item["passage_id"])
            ranked.append(item["passage_id"])
    return ranked


def _raise_schema_errors(validator: Any, instance: Any, label: str) -> None:
    errors = sorted(validator.iter_errors(instance), key=lambda error: [str(part) for part in error.absolute_path])
    if errors:
        raise R1EvaluationError(f"{label} schema validation failed: {errors[0].message}")


def _repository_root(path: Path) -> Path:
    for candidate in (Path.cwd(), *path.resolve().parents):
        if (candidate / "outputs" / "rag_bm25_v1" / "passages.jsonl").is_file():
            return candidate
    raise R1EvaluationError("repository root with frozen R1 corpus not found")


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 6) if values else None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return round(ordered[index], 6)
