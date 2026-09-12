from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from litflow.rag.retrieval_quality_r1 import (
    R1EvaluationError,
    assert_tuning_split,
    canonical_sha256,
    evaluate_rankings,
    load_all_r1_records,
    load_r1_manifest,
    load_r1_records,
    validate_json_schema_documents,
)


ROOT = Path(__file__).parents[1]
BASE = ROOT / "docs" / "deep_research" / "retrieval_quality_r1"
MANIFEST = BASE / "r1_dataset.manifest.json"
CORPUS = ROOT / "outputs" / "rag_bm25_v1" / "passages.jsonl"


def test_three_schemas_parse_as_draft_2020_12():
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((BASE / "schemas").glob("*.json"))]
    assert len(schemas) == 3
    assert all(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema" for schema in schemas)


def test_real_r1_files_pass_json_schema_validation():
    pytest.importorskip("jsonschema")
    validate_json_schema_documents(MANIFEST)


def test_sha256_is_case_insensitive_but_strictly_well_formed(tmp_path: Path):
    digest = "D099DC9EF22678AF17FFBB12FC5198C9A6FCE71D56576DDE6F2B62984B8A7DE6"
    assert canonical_sha256(digest) == digest.lower()
    for invalid in (digest[:-1], digest + "0", "z" * 64):
        with pytest.raises(R1EvaluationError, match="exactly 64 hexadecimal"):
            canonical_sha256(invalid)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["corpus"]["corpus_sha256"] = manifest["corpus"]["corpus_sha256"].upper()
    uppercase = tmp_path / "manifest.json"
    uppercase.write_text(json.dumps(manifest), encoding="utf-8")
    load_r1_manifest(uppercase)


def test_real_sha256_mismatch_is_rejected(tmp_path: Path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["corpus"]["corpus_sha256"] = "0" * 64
    changed = tmp_path / "manifest.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(R1EvaluationError, match="frozen corpus SHA-256 mismatch"):
        load_r1_manifest(changed)


def test_twenty_historical_records_are_canonical_reviewed_records():
    rows = load_r1_records(MANIFEST, split="development")
    assert len(rows) == 20
    assert all(row["split"] == "development" and row["review_status"] == "reviewed" for row in rows)
    assert Counter(row["source_review_status"] for row in rows) == {"human_reviewed_pilot": 19, "human_reviewed_pilot_qrels_v1_1": 1}
    assert all(row["source_path"].endswith("queries_human_reviewed_pilot_qrels_v1_1.json") for row in rows)


def test_pending_counts_quotas_and_ids_are_isolated():
    dev = load_r1_records(MANIFEST, split="dev_hard_negative", allow_pending=True)
    held = load_r1_records(MANIFEST, split="held_out", allow_pending=True)
    reviewed = load_r1_records(MANIFEST, split="development")
    assert len(dev) == 12 and len(held) == 16
    assert Counter(row["query_type"] for row in dev) == {"no_answer": 6, "hard_negative": 6}
    assert Counter(row["query_type"] for row in held) == {"single_paper": 8, "cross_paper": 4, "in_domain_no_answer": 2, "near_miss_hard_negative": 2}
    assert all(row["review_status"] == "pending_review" for row in dev + held)
    all_ids = [row["query_id"] for row in reviewed + dev + held]
    assert len(all_ids) == len(set(all_ids)) == 48
    assert len(load_all_r1_records(MANIFEST, allow_pending=True)) == 48


def test_pending_json_and_review_csv_match():
    pending = json.loads((BASE / "pending_candidates.json").read_text(encoding="utf-8"))["queries"]
    with (BASE / "pending_candidates.review.csv").open(encoding="utf-8-sig", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    assert [row["query_id"] for row in pending] == [row["query_id"] for row in review_rows]
    for record, review in zip(pending, review_rows, strict=True):
        assert review["split"] == record["split"]
        assert review["query_type"] == record["query_type"]
        assert review["expected_answerable"].lower() == str(record["expected_answerable"]).lower()
        assert review["review_status"] == record["review_status"] == "pending_review"


def test_candidate_qrels_resolve_to_declared_corpus_sources():
    passages = {row["passage_id"]: row for row in _jsonl(CORPUS)}
    pending = json.loads((BASE / "pending_candidates.json").read_text(encoding="utf-8"))["queries"]
    for record in pending:
        if not record["expected_answerable"]:
            assert record["relevant_paper_keys"] == [] and record["relevant_passage_ids"] == []
        for passage_id in record["relevant_passage_ids"]:
            assert passage_id in passages
            assert passages[passage_id]["paper_key"] in record["relevant_paper_keys"]
            assert passage_id.split(":", 1)[0] == passages[passage_id]["paper_key"]


def test_pending_review_is_fail_closed_for_formal_evaluation():
    with pytest.raises(R1EvaluationError, match="pending_review"):
        load_r1_records(MANIFEST, split="held_out")
    pending = load_r1_records(MANIFEST, split="held_out", allow_pending=True)
    with pytest.raises(R1EvaluationError, match="reviewed records"):
        evaluate_rankings(pending, [{"query_id": row["query_id"], "results": []} for row in pending], retriever_mode="bm25_zh_raw")


def test_held_out_is_never_a_tuning_split():
    assert_tuning_split("development")
    assert_tuning_split("dev_hard_negative")
    with pytest.raises(R1EvaluationError, match="held-out"):
        assert_tuning_split("held_out")


def test_evaluator_rejects_unapproved_retriever_modes():
    with pytest.raises(R1EvaluationError, match="unsupported R1 retriever mode"):
        evaluate_rankings([], [], retriever_mode="reranker")


def test_metrics_cover_multiple_qrels_graded_ndcg_and_latency():
    records = [{"query_id": "q1", "split": "development", "query_zh": "q", "query_en": "q", "query_type": "method", "expected_answerable": True, "relevant_paper_keys": ["a"], "relevant_passage_ids": ["a:p1", "a:p2"], "gold_evidence_summary": "gold", "review_status": "reviewed", "source_review_status": "source", "source_path": "source.json", "source_record_sha256": "0" * 64, "relevance_grades": {"a:p1": 3, "a:p2": 1}}]
    report = evaluate_rankings(records, [{"query_id": "q1", "results": [{"passage_id": "a:other"}, {"passage_id": "a:p2"}, {"passage_id": "a:p1"}], "latency_ms": 5.0}], retriever_mode="hybrid_zh_windowed")
    assert report["retriever_mode"] == "hybrid_zh_windowed"
    assert report["metrics"]["recall_at_5"] == 1.0
    assert report["metrics"]["recall_at_20"] == 1.0
    assert report["metrics"]["mrr_at_10"] == 0.5
    assert 0 < report["metrics"]["ndcg_at_10"] < 1
    assert report["answerable_retrieval_success_at_10"] == 1.0
    assert report["latency_ms"] == {"mean": 5.0, "p50": 5.0, "p95": 5.0, "count": 1}


def test_empty_answerable_and_no_answer_results_have_explicit_metrics():
    common = {"split": "development", "query_zh": "q", "query_en": "q", "query_type": "method", "gold_evidence_summary": "gold", "review_status": "reviewed", "source_review_status": "source", "source_path": "source.json", "source_record_sha256": "0" * 64}
    records = [{**common, "query_id": "q1", "expected_answerable": True, "relevant_paper_keys": ["a"], "relevant_passage_ids": ["a:p1"]}, {**common, "query_id": "q2", "expected_answerable": False, "relevant_paper_keys": [], "relevant_passage_ids": []}]
    empty = evaluate_rankings(records, [{"query_id": "q1", "results": []}, {"query_id": "q2", "results": []}], retriever_mode="bm25_en")
    assert empty["metrics"] == {"recall_at_5": 0.0, "recall_at_10": 0.0, "recall_at_20": 0.0, "mrr_at_10": 0.0, "ndcg_at_10": 0.0}
    assert empty["answerable_retrieval_success_at_20"] == 0.0
    assert empty["no_answer_false_positive_rate_at_10"] == 0.0
    false_positive = evaluate_rankings(records, [{"query_id": "q1", "results": []}, {"query_id": "q2", "results": [{"passage_id": "a:p2"}]}], retriever_mode="bm25_en")
    assert false_positive["no_answer_false_positive_rate_at_10"] == 1.0


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
