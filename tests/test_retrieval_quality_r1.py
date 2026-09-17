from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from litflow.rag.retrieval_quality_r1 import (
    R1EvaluationError,
    apply_top_score_gate,
    assert_tuning_split,
    calibrate_top_score_gate,
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


@pytest.fixture
def r1_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Build a tiny synthetic, hash-consistent corpus around tracked R1 qrels."""
    root = tmp_path / "r1-fixture-repository"
    base = root / "docs" / "deep_research" / "retrieval_quality_r1"
    (base / "schemas").mkdir(parents=True)
    original = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = json.loads(json.dumps(original))
    for schema in (BASE / "schemas").glob("*.json"):
        shutil.copyfile(schema, base / "schemas" / schema.name)

    package_paths: dict[str, Path] = {}
    package_payloads: dict[str, dict[str, object]] = {}
    for key in ("development_reviewed", "pending_candidates", "reviewed_candidates"):
        relative = Path(manifest[key]["path"])
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
        package_paths[key] = target
        package_payloads[key] = json.loads(target.read_text(encoding="utf-8"))
    csv_relative = Path(manifest["pending_candidates"]["review_csv"])
    csv_path = root / csv_relative
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / csv_relative, csv_path)

    passage_ids = sorted({
        passage_id
        for package in package_payloads.values()
        for record in package["queries"]
        for passage_id in record["relevant_passage_ids"]
    })
    paper_keys = sorted({passage_id.split(":", 1)[0] for passage_id in passage_ids})
    assert len(paper_keys) <= 10 and len(passage_ids) <= 185
    paper_keys.extend(f"R1FIXTURE{index:02d}" for index in range(10 - len(paper_keys)))
    source_hashes = {key: hashlib.sha256(f"fixture-source:{key}".encode()).hexdigest() for key in paper_keys}

    def passage(passage_id: str, paper_key: str, text: str) -> dict[str, object]:
        return {
            "passage_id": passage_id,
            "paper_key": paper_key,
            "citation_key": f"fixture-{paper_key}",
            "title": f"Synthetic fixture {paper_key}",
            "chunk_id": passage_id.split(":", 1)[1],
            "page_start": 1,
            "page_end": 1,
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "source_context_sha256": source_hashes[paper_key],
        }

    rows = [passage(passage_id, passage_id.split(":", 1)[0], f"Synthetic CI passage for {passage_id}.") for passage_id in passage_ids]
    next_id = 0
    while len(rows) < 185:
        paper_key = paper_keys[next_id % len(paper_keys)]
        passage_id = f"{paper_key}:{paper_key}_fixture_{next_id:04d}"
        if passage_id not in {row["passage_id"] for row in rows}:
            rows.append(passage(passage_id, paper_key, f"Synthetic filler passage {next_id}."))
        next_id += 1
    corpus_rel = Path("outputs/rag_bm25_v1/passages.jsonl")
    corpus_path = root / corpus_rel
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_bytes = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
    corpus_path.write_bytes(corpus_bytes)
    corpus_sha = hashlib.sha256(corpus_bytes).hexdigest()

    corpus_manifest = {"corpus_id": "synthetic-r1-ci", "paper_count": 10, "passage_count": 185, "corpus_sha256": corpus_sha}
    corpus_manifest_path = root / "outputs" / "rag_bm25_v1" / "corpus_manifest.json"
    corpus_manifest_bytes = (json.dumps(corpus_manifest, sort_keys=True) + "\n").encode()
    corpus_manifest_path.write_bytes(corpus_manifest_bytes)
    passage_manifest = {
        "manifest_id": "retrieval-quality-r1-passage-hashes-v1",
        "corpus_path": corpus_rel.as_posix(),
        "corpus_sha256": corpus_sha,
        "passage_count": len(rows),
        "passages": [{key: row[key] for key in ("passage_id", "paper_key", "text_sha256", "source_context_sha256")} for row in rows],
    }
    passage_manifest_path = base / "passage_hashes.json"
    passage_manifest_path.write_text(json.dumps(passage_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def canonical_hash(path: Path) -> str:
        payload = json.loads(path.read_text(encoding="utf-8"))
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    manifest["corpus"].update({
        "path": corpus_rel.as_posix(),
        "manifest_path": "outputs/rag_bm25_v1/corpus_manifest.json",
        "corpus_sha256": corpus_sha,
        "manifest_sha256": hashlib.sha256(corpus_manifest_bytes).hexdigest(),
        "passage_hashes_path": "docs/deep_research/retrieval_quality_r1/passage_hashes.json",
        "passage_hashes_sha256": canonical_hash(passage_manifest_path),
        "paper_count": 10,
        "passage_count": 185,
    })
    for key, target in package_paths.items():
        manifest[key]["sha256"] = canonical_hash(target)
    manifest["development_reviewed"]["source_path"] = manifest["development_reviewed"]["path"]
    manifest["development_reviewed"]["source_sha256"] = hashlib.sha256(package_paths["development_reviewed"].read_bytes()).hexdigest()
    manifest["pending_candidates"]["review_csv_sha256"] = hashlib.sha256(csv_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode()).hexdigest()
    manifest["reviewed_candidates"]["source_sha256"] = manifest["pending_candidates"]["sha256"]
    manifest_path = base / "r1_dataset.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path, corpus_path


def test_three_schemas_parse_as_draft_2020_12():
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((BASE / "schemas").glob("*.json"))]
    assert len(schemas) == 3
    assert all(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema" for schema in schemas)


def test_real_r1_records_pass_json_schema_validation_with_synthetic_corpus(r1_fixture):
    validate_json_schema_documents(r1_fixture[0])


def test_sha256_is_case_insensitive_but_strictly_well_formed(tmp_path: Path, r1_fixture):
    digest = "D099DC9EF22678AF17FFBB12FC5198C9A6FCE71D56576DDE6F2B62984B8A7DE6"
    assert canonical_sha256(digest) == digest.lower()
    for invalid in (digest[:-1], digest + "0", "z" * 64):
        with pytest.raises(R1EvaluationError, match="exactly 64 hexadecimal"):
            canonical_sha256(invalid)
    manifest = json.loads(r1_fixture[0].read_text(encoding="utf-8"))
    manifest["corpus"]["corpus_sha256"] = manifest["corpus"]["corpus_sha256"].upper()
    uppercase = r1_fixture[0].parent / "manifest.uppercase.json"
    uppercase.write_text(json.dumps(manifest), encoding="utf-8")
    load_r1_manifest(uppercase)


def test_real_sha256_mismatch_is_rejected(r1_fixture):
    manifest = json.loads(r1_fixture[0].read_text(encoding="utf-8"))
    manifest["corpus"]["corpus_sha256"] = "0" * 64
    changed = r1_fixture[0].parent / "manifest.mismatch.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(R1EvaluationError, match="frozen corpus SHA-256 mismatch"):
        load_r1_manifest(changed)


def test_twenty_historical_records_are_canonical_reviewed_records(r1_fixture):
    rows = load_r1_records(r1_fixture[0], split="development")
    assert len(rows) == 20
    assert all(row["split"] == "development" and row["review_status"] == "reviewed" for row in rows)
    assert Counter(row["source_review_status"] for row in rows) == {"human_reviewed_pilot": 19, "human_reviewed_pilot_qrels_v1_1": 1}
    assert all(row["source_path"].endswith("queries_human_reviewed_pilot_qrels_v1_1.json") for row in rows)


def test_pending_counts_quotas_and_ids_are_isolated(r1_fixture):
    dev = load_r1_records(r1_fixture[0], split="dev_hard_negative", allow_pending=True)
    held = load_r1_records(r1_fixture[0], split="held_out", allow_pending=True)
    reviewed = load_r1_records(r1_fixture[0], split="development")
    assert len(dev) == 12 and len(held) == 16
    assert Counter(row["query_type"] for row in dev) == {"hard_negative": 12}
    assert Counter(row["query_type"] for row in held) == {"single_paper": 8, "cross_paper": 4, "in_domain_no_answer": 2, "near_miss_hard_negative": 2}
    assert all(row["review_status"] == "reviewed" for row in dev + held)
    all_ids = [row["query_id"] for row in reviewed + dev + held]
    assert len(all_ids) == len(set(all_ids)) == 48
    assert len(load_all_r1_records(r1_fixture[0], allow_pending=True)) == 48
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


def test_candidate_qrels_resolve_to_declared_corpus_sources(r1_fixture):
    passages = {row["passage_id"]: row for row in _jsonl(r1_fixture[1])}
    pending = json.loads((BASE / "pending_candidates.json").read_text(encoding="utf-8"))["queries"]
    for record in pending:
        if not record["expected_answerable"]:
            assert record["relevant_paper_keys"] == [] and record["relevant_passage_ids"] == []
        for passage_id in record["relevant_passage_ids"]:
            assert passage_id in passages
            assert passages[passage_id]["paper_key"] in record["relevant_paper_keys"]
            assert passage_id.split(":", 1)[0] == passages[passage_id]["paper_key"]


def test_held_out_passage_overlap_is_explicit_and_claim_overlap_is_false(r1_fixture):
    reviewed = load_r1_records(r1_fixture[0], split="development")
    held = load_r1_records(r1_fixture[0], split="held_out", allow_pending=True)
    development_passages = {passage_id for row in reviewed for passage_id in row["relevant_passage_ids"]}
    for row in held:
        actual_overlap = sorted(set(row["relevant_passage_ids"]) & development_passages)
        declared = row["development_overlap"]
        assert declared["passage_overlap"] == bool(actual_overlap)
        assert declared["answer_claim_overlap"] is False
        assert declared["independence_note"]
    assert [row["query_id"] for row in held if row["development_overlap"]["passage_overlap"]] == ["H007"]


def test_pending_source_remains_fail_closed_but_frozen_records_are_reviewed(r1_fixture):
    pending = json.loads((BASE / "pending_candidates.json").read_text(encoding="utf-8"))["queries"]
    assert all(row["review_status"] == "pending_review" for row in pending)
    with pytest.raises(R1EvaluationError, match="reviewed records"):
        evaluate_rankings(pending, [{"query_id": row["query_id"], "results": []} for row in pending], retriever_mode="bm25_zh_raw")
    assert all(row["review_status"] == "reviewed" for row in load_r1_records(r1_fixture[0], split="held_out"))


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


def test_round4_gate_is_reproducible_from_development_only(r1_fixture):
    config = json.loads((BASE / "round4_relevance_gate.json").read_text(encoding="utf-8"))
    records = load_r1_records(r1_fixture[0], split="development") + load_r1_records(r1_fixture[0], split="dev_hard_negative")
    rankings = json.loads((BASE / "results" / "r1_rankings.json").read_text(encoding="utf-8"))["development"]["bm25_en"]
    actual = calibrate_top_score_gate(records, rankings, retriever_mode="bm25_en", minimum_answerable_success_at_10=0.85)
    assert actual["threshold"] == config["gate"]["threshold"] == 11.398627187607
    assert actual["development_report"]["answerable_retrieval_success_at_10"] == config["calibration"]["after"]["answerable_retrieval_success_at_10"]
    assert actual["development_report"]["no_answer_false_positive_rate_at_10"] == config["calibration"]["after"]["no_answer_false_positive_rate_at_10"]
    assert config["held_out"] == {"run_count": 0, "replay_count": 0, "used_for_calibration": False, "claim": "not_independently_validated"}


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


def test_top_score_gate_is_calibrated_on_development_and_preserves_rankings():
    common = {"split": "development", "query_zh": "q", "query_en": "q", "query_type": "method", "gold_evidence_summary": "gold", "review_status": "reviewed", "source_review_status": "source", "source_path": "source.json", "source_record_sha256": "0" * 64}
    records = [
        {**common, "query_id": "a", "expected_answerable": True, "relevant_paper_keys": ["p"], "relevant_passage_ids": ["p:gold"]},
        {**common, "query_id": "n", "expected_answerable": False, "relevant_paper_keys": [], "relevant_passage_ids": []},
    ]
    rankings = [
        {"query_id": "a", "results": [{"passage_id": "p:gold", "score": 2.0}], "latency_ms": 1.0},
        {"query_id": "n", "results": [{"passage_id": "p:false", "score": 1.0}], "latency_ms": 1.0},
    ]
    calibration = calibrate_top_score_gate(records, rankings, retriever_mode="bm25_en", minimum_answerable_success_at_10=1.0)
    assert calibration["threshold"] == 2.0
    gated = apply_top_score_gate(rankings, calibration["threshold"])
    assert gated[0]["results"] == rankings[0]["results"]
    assert gated[1]["results"] == []
    assert calibration["development_report"]["no_answer_false_positive_rate_at_10"] == 0.0


def test_gate_calibration_rejects_held_out_records():
    records = [{"query_id": "h", "split": "held_out"}]
    with pytest.raises(R1EvaluationError, match="held-out"):
        calibrate_top_score_gate(records, [{"query_id": "h", "results": []}], retriever_mode="bm25_en", minimum_answerable_success_at_10=0.8)


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
