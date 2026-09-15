from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from litflow.rag.retrieval_quality_r1 import (
    R1EvaluationError,
    assert_tuning_split,
    canonical_sha256,
    evaluate_rankings,
    load_all_r1_records,
    load_r1_manifest,
    load_r1_records,
    select_development_mode,
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
    assert Counter(row["query_type"] for row in dev) == {"hard_negative": 12}
    assert Counter(row["query_type"] for row in held) == {"single_paper": 8, "cross_paper": 4, "in_domain_no_answer": 2, "near_miss_hard_negative": 2}
    assert all(row["review_status"] == "reviewed" for row in dev + held)
    all_ids = [row["query_id"] for row in reviewed + dev + held]
    assert len(all_ids) == len(set(all_ids)) == 48
    assert len(load_all_r1_records(MANIFEST, allow_pending=True)) == 48
    claim_families = [row["answer_claim_family"] for row in reviewed + dev + held]
    assert len(claim_families) == len(set(claim_families)) == 48


def test_pending_json_and_review_csv_match():
    pending = json.loads((BASE / "pending_candidates.json").read_text(encoding="utf-8"))["queries"]
    with (BASE / "pending_candidates.review.csv").open(encoding="utf-8-sig", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    assert [row["query_id"] for row in pending] == [row["query_id"] for row in review_rows]
    for record, review in zip(pending, review_rows, strict=True):
        assert review["split"] == record["split"]
        assert review["query_type"] == record["query_type"]
        assert review["expected_answerable"].lower() == str(record["expected_answerable"]).lower()
        assert review["answer_claim_family"] == record["answer_claim_family"]
        assert review["review_status"] == record["review_status"] == "pending_review"
        assert review["answerable_correct"] == review["relevant_passages_correct"] == "true"
        assert review["review_decision"] == "approved"
        assert review["reviewer"] == "project_owner"
        assert review["reviewed_at"] == "2026-09-15T06:56:24Z"
        if record["split"] == "held_out":
            overlap = record["development_overlap"]
            assert review["passage_overlap"] == str(overlap["passage_overlap"]).lower()
            assert review["answer_claim_overlap"] == "false"
            assert review["independence_note"] == overlap["independence_note"]


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


def test_held_out_passage_overlap_is_explicit_and_claim_overlap_is_false():
    reviewed = load_r1_records(MANIFEST, split="development")
    held = load_r1_records(MANIFEST, split="held_out", allow_pending=True)
    development_passages = {passage_id for row in reviewed for passage_id in row["relevant_passage_ids"]}
    for row in held:
        actual_overlap = sorted(set(row["relevant_passage_ids"]) & development_passages)
        declared = row["development_overlap"]
        assert declared["passage_overlap"] == bool(actual_overlap)
        assert declared["answer_claim_overlap"] is False
        assert declared["independence_note"]
    assert [row["query_id"] for row in held if row["development_overlap"]["passage_overlap"]] == ["H007"]


def test_pending_source_remains_fail_closed_but_frozen_records_are_reviewed():
    pending = json.loads((BASE / "pending_candidates.json").read_text(encoding="utf-8"))["queries"]
    assert all(row["review_status"] == "pending_review" for row in pending)
    with pytest.raises(R1EvaluationError, match="reviewed records"):
        evaluate_rankings(pending, [{"query_id": row["query_id"], "results": []} for row in pending], retriever_mode="bm25_zh_raw")
    assert all(row["review_status"] == "reviewed" for row in load_r1_records(MANIFEST, split="held_out"))


def test_project_owner_review_conditions_are_frozen():
    frozen = json.loads((BASE / "reviewed_candidates.json").read_text(encoding="utf-8"))["queries"]
    assert len(frozen) == 28
    assert all(row["reviewer"] == "project_owner" and row["review_decision"] == "approved" for row in frozen)
    assert all(row["answerable_correct"] and row["relevant_passages_correct"] for row in frozen)
    by_id = {row["query_id"]: row for row in frozen}
    assert not any(passage_id.endswith("JRIUZQ58_chunk_0029") for passage_id in by_id["H012"]["relevant_passage_ids"])
    assert by_id["H007"]["development_overlap"] == {"passage_overlap": True, "overlapping_query_ids": ["Q08", "Q15"], "answer_claim_overlap": False, "independence_note": "The passages overlap development qrels, but development asks inference speed and small/multi-scale methods, not the mAP50/F1 result."}
    assert "must not support a claim" in by_id["H010"]["reviewer_notes"]


def test_formal_result_reproduces_development_selection_and_one_held_out_run():
    result = json.loads((BASE / "results" / "r1_result.json").read_text(encoding="utf-8"))
    plan = json.loads((BASE / "r1_evaluation_plan.json").read_text(encoding="utf-8"))
    assert select_development_mode(result["development"], plan["modes"]) == result["selected_mode"] == "bm25_en"
    assert result["split_policy"]["held_out_execution_count"] == 1
    assert result["split_policy"]["held_out_used_for_tuning"] is False
    assert result["held_out"]["query_count"] == 16
    assert result["limitations"]["h007"].startswith("query/claim-held-out only")


def test_result_manifest_freezes_result_and_rankings_bytes():
    manifest = json.loads((BASE / "results" / "r1_result_manifest.json").read_text(encoding="utf-8"))
    assert manifest["held_out_execution_count"] == 1
    assert manifest["held_out_retry_count"] == 0
    for item in manifest["files"]:
        path = BASE / "results" / item["path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        assert len(canonical) == item["canonical_bytes"]
        assert hashlib.sha256(canonical).hexdigest() == item["canonical_sha256"]


def test_formal_rankings_pass_schema_and_match_frozen_splits():
    schema = json.loads((BASE / "schemas" / "result.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    rankings = json.loads((BASE / "results" / "r1_rankings.json").read_text(encoding="utf-8"))
    plan = json.loads((BASE / "r1_evaluation_plan.json").read_text(encoding="utf-8"))
    assert list(rankings["development"]) == plan["modes"]
    assert list(rankings["held_out"]) == ["bm25_en"]
    for split in rankings.values():
        for records in split.values():
            assert all(not list(validator.iter_errors(record)) for record in records)
            assert all(len(record["results"]) <= 20 for record in records)


def test_evaluation_plan_binds_dataset_and_model_manifests():
    plan = json.loads((BASE / "r1_evaluation_plan.json").read_text(encoding="utf-8"))
    for filename, field in (("r1_dataset.manifest.json", "dataset_manifest_sha256"), ("model_asset_manifest.json", "model_asset_manifest_sha256")):
        payload = json.loads((BASE / filename).read_text(encoding="utf-8"))
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        assert hashlib.sha256(canonical).hexdigest() == plan[field]


def test_model_asset_manifest_contains_only_relative_frozen_files():
    manifest = json.loads((BASE / "model_asset_manifest.json").read_text(encoding="utf-8"))
    assert manifest["repository"] == "intfloat/multilingual-e5-small"
    assert manifest["revision"] == "053834db62d809d8f124a76b687fbd948e13ef3e"
    assert manifest["encoder_contract"]["local_files_only"] is True
    assert manifest["encoder_contract"]["hidden_size"] == 384
    assert len(manifest["files"]) == 6
    assert all(not Path(item["path"]).is_absolute() and len(item["sha256"]) == 64 for item in manifest["files"])


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
