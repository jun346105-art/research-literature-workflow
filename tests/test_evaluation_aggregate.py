import csv
import hashlib
import json
from pathlib import Path

import pytest

from litflow.evaluation_aggregate import EvaluationAggregateError, aggregate_evaluation_pilot, nearest_rank_percentile


def test_aggregate_uses_canonical_headers_and_call_metrics(tmp_path):
    runs, expected_hashes = _make_runs(tmp_path)
    out_dir = tmp_path / "aggregate"

    report = aggregate_evaluation_pilot(
        runs,
        out_dir,
        expected_reviewed_sha256=expected_hashes,
        repo_root=tmp_path,
        command_args=["litflow", "aggregate-evaluation-pilot"],
        aggregator_git_commit_sha="aggregator-test-sha",
    )

    with (out_dir / "human_review_aggregate.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "paper_key", "run_name", "review_id", "run_id", "zotero_key", "method",
            "evidence_index", "claim", "chunk_id", "page_start", "page_end", "evidence_text",
            "automatic_grounding_status", "automatic_failure_type", "support_label", "needs_revision",
            "acceptance", "reviewer_notes_raw", "reviewer_notes_integrity",
        ]
        rows = list(reader)
    assert len(rows) == 6
    assert rows[0]["claim"] == "中文 claim"
    assert rows[0]["reviewer_notes_raw"] == "正常中文批注"
    assert rows[0]["reviewer_notes_integrity"] == "ok"
    assert rows[1]["reviewer_notes_raw"] == "?????"
    assert rows[1]["reviewer_notes_integrity"] == "legacy_encoding_lost"
    assert report["micro_aggregate"]["calls"]["total"] == 9
    assert report["micro_aggregate"]["tokens"]["input_tokens"] == 9
    assert report["micro_aggregate"]["provider_usage_statuses"] == {"provider_reported": 9}
    assert report["human_review_aggregate"]["baseline"]["supported"]["numerator"] == 3
    assert report["human_review_aggregate"]["proposed"]["supported"]["numerator"] == 3
    assert report["known_limitations"] == [
        "Development pilot only; not a held-out benchmark.",
        "Baseline and Proposed claims are not paired claim-by-claim.",
        "Human labels are project-author review with AI-assisted translation, not independent blinded expert annotation.",
        "Exact grounding does not establish semantic correctness.",
        "Candidate chunk coverage does not equal retrieval recall.",
        "Legacy reviewer notes contain irreversible encoding loss and are excluded from metrics.",
    ]
    serialized_summary = json.dumps(report, ensure_ascii=False)
    assert "?" not in serialized_summary
    for paper in report["per_paper"]:
        assert paper["artifact_paths"]["pdf"] == {
            "path_type": "private_local_path_redacted",
            "sha256": _sha256(tmp_path / "paper.pdf"),
        }
        assert all("C:\\Users" not in json.dumps(path) for path in paper["artifact_paths"].values())
    reproduction = json.loads((out_dir / "reproduction_manifest.json").read_text(encoding="utf-8"))
    assert reproduction["aggregator_git_commit_sha"] == "aggregator-test-sha"
    assert len(reproduction["aggregator_module_sha256"]) == 64
    assert all(".aggregate.tmp-" not in item["path"] for item in reproduction["outputs"])
    assert reproduction["original_command"] == ["litflow", "aggregate-evaluation-pilot"]
    assert reproduction["replay_command_template"] == ["litflow", "aggregate-evaluation-pilot"]


def test_replay_template_replaces_output_directory(tmp_path):
    runs, expected_hashes = _make_runs(tmp_path)
    out_dir = tmp_path / "aggregate"
    aggregate_evaluation_pilot(
        runs,
        out_dir,
        expected_reviewed_sha256=expected_hashes,
        repo_root=tmp_path,
        command_args=["litflow", "aggregate-evaluation-pilot", "--out-dir", str(out_dir)],
        aggregator_git_commit_sha="test",
    )

    reproduction = json.loads((out_dir / "reproduction_manifest.json").read_text(encoding="utf-8"))
    assert reproduction["original_command"][-1] == str(out_dir)
    assert reproduction["replay_command_template"][-1] == "<NEW_EMPTY_OUTPUT_DIR>"


def test_aggregate_rejects_mismatched_reviewed_hash_before_output(tmp_path):
    runs, expected_hashes = _make_runs(tmp_path)
    expected_hashes["P1"] = "0" * 64
    out_dir = tmp_path / "aggregate"

    with pytest.raises(EvaluationAggregateError, match="reviewed CSV SHA-256 mismatch"):
        aggregate_evaluation_pilot(runs, out_dir, expected_reviewed_sha256=expected_hashes, repo_root=tmp_path, aggregator_git_commit_sha="test")

    assert not out_dir.exists()


def test_aggregate_rejects_inconsistent_run_configuration_before_output(tmp_path):
    runs, expected_hashes = _make_runs(tmp_path)
    manifest = json.loads((runs[1] / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["temperature"] = 1
    (runs[1] / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    out_dir = tmp_path / "aggregate"

    with pytest.raises(EvaluationAggregateError, match="configuration mismatch"):
        aggregate_evaluation_pilot(runs, out_dir, expected_reviewed_sha256=expected_hashes, repo_root=tmp_path, aggregator_git_commit_sha="test")

    assert not out_dir.exists()


def test_aggregate_rejects_nonempty_output_directory(tmp_path):
    runs, expected_hashes = _make_runs(tmp_path)
    out_dir = tmp_path / "aggregate"
    out_dir.mkdir()
    (out_dir / "existing.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(EvaluationAggregateError, match="already exists"):
        aggregate_evaluation_pilot(runs, out_dir, expected_reviewed_sha256=expected_hashes, repo_root=tmp_path, aggregator_git_commit_sha="test")


def test_aggregate_leaves_no_final_output_when_writing_fails(tmp_path, monkeypatch):
    runs, expected_hashes = _make_runs(tmp_path)
    out_dir = tmp_path / "aggregate"

    def fail_write(*_args, **_kwargs):
        raise OSError("write failed")

    monkeypatch.setattr("litflow.evaluation_aggregate._write_outputs", fail_write)
    with pytest.raises(OSError, match="write failed"):
        aggregate_evaluation_pilot(runs, out_dir, expected_reviewed_sha256=expected_hashes, repo_root=tmp_path, aggregator_git_commit_sha="test")

    assert not out_dir.exists()
    assert not list(tmp_path.glob(".aggregate.tmp-*"))


def test_nearest_rank_percentile():
    assert nearest_rank_percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert nearest_rank_percentile([1, 2, 3, 4, 5], 0.95) == 5


def _make_runs(tmp_path: Path) -> tuple[list[Path], dict[str, str]]:
    research = tmp_path / "research.txt"
    research.write_text("research context", encoding="utf-8")
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"pdf")
    papers = []
    for index, key in enumerate(("P1", "P2", "P3"), 1):
        context = tmp_path / f"{key}.json"
        context.write_text(json.dumps({"chunks": [{"chunk_id": f"{key}_chunk_0001", "text": "source", "page_start": 1, "page_end": 1}]}), encoding="utf-8")
        papers.append({"zotero_key": key, "source_clean_context_path": context.name, "clean_context_sha256": _sha256(context), "pdf_path": str(pdf), "pdf_sha256": _sha256(pdf)})
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps({"papers": papers}), encoding="utf-8")

    runs, hashes = [], {}
    for index, key in enumerate(("P1", "P2", "P3"), 1):
        run = tmp_path / f"run_{key}"
        (run / "papers" / key / "baseline").mkdir(parents=True)
        (run / "papers" / key / "proposed").mkdir(parents=True)
        manifest = {
            "model": "model", "temperature": 0, "git_commit_sha": "run-sha", "request_config": {"thinking_mode": "disabled", "response_format": {"type": "json_object"}},
            "context_window": {"context_limit_tokens": 100, "max_output_tokens": 10, "safety_margin_tokens": 1}, "selected_paper_keys": [key],
            "plan": {"manifest": "frozen.json", "research_context": {"path": "research.txt", "sha256": _sha256(research)}, "selected_paper_keys": [key], "papers": [{"zotero_key": key, "chunk_count": 1, "baseline_prompt_version": "b", "baseline_content_schema_version": "bc", "proposed_candidate_prompt_version": "c", "proposed_final_prompt_version": "f"}]},
        }
        _write_json(run / "run_manifest.json", manifest)
        _write_json(run / "input_verification.json", {"verified": True, "papers": [key]})
        _write_json(run / "errors.json", [])
        _write_json(run / "papers" / key / "baseline" / "metrics.json", {"evidence_links_count": 1, "exact_grounding_pass_count": 0, "exact_grounding_failure_count": 1, "evidence_text_not_found_count": 1, "page_range_mismatch_count": 0, "chunk_id_not_found_count": 0, "raw_json_parse_valid": True, "baseline_content_schema_valid": True, "baseline_scoring_view_valid": True})
        _write_json(run / "papers" / key / "proposed" / "metrics.json", {"final_selected_evidence_count": 1, "exact_grounding_pass_count": 1, "exact_grounding_failure_count": 0, "schema_valid": True, "total_llm_calls": 999, "usage_status": "usage_unavailable"})
        _write_json(run / "papers" / key / "proposed" / "evidence_candidate_bank.json", {"candidates": [{"chunk_id": f"{key}_chunk_0001", "anchoring_method": "exact_match"}], "failures": [{"chunk_id": f"{key}_chunk_0001", "error_type": "evidence_anchor_not_found"}]})
        _write_json(run / "papers" / key / "proposed" / "candidate_report.json", {"anchoring_methods": {"exact_match": 1}, "failure_types": {"evidence_anchor_not_found": 1}})
        _write_json(run / "papers" / key / "proposed" / "final_note.json", {})
        calls = [
            _call("baseline_raw", 1, 10 + index, 1),
            _call("proposed_candidate_chunk", 1, 11 + index, 1),
            _call("proposed_final_note", 1, 12 + index, 1),
        ]
        _write_json(run / "call_metrics.json", calls)
        rows = [
            {"run_id": run.name, "zotero_key": key, "method": "baseline", "evidence_index": "1", "claim": "中文 claim", "chunk_id": f"{key}_chunk_0001", "page_start": "1", "page_end": "1", "evidence_text": "source", "automatic_grounding_status": "fail", "automatic_failure_type": "evidence_text_not_found", "support_label": "supported", "needs_revision": "no", "acceptance": "accept", "reviewer_notes": "正常中文批注"},
            {"run_id": run.name, "zotero_key": key, "method": "proposed", "evidence_index": "1", "claim": "中文 claim", "chunk_id": f"{key}_chunk_0001", "page_start": "1", "page_end": "1", "evidence_text": "source", "automatic_grounding_status": "pass", "automatic_failure_type": "", "support_label": "supported", "needs_revision": "no", "acceptance": "accept", "reviewer_notes": "?????"},
        ]
        reviewed = run / "manual_claim_evidence_review_reviewed.csv"
        _write_csv(reviewed, rows)
        hashes[key] = _sha256(reviewed)
        runs.append(run)
    return runs, hashes


def _call(stage: str, attempt: int, latency_ms: int, tokens: int) -> dict:
    return {"stage": stage, "attempt": attempt, "status": "success", "usage_status": "provider_reported", "input_tokens": tokens, "output_tokens": tokens, "total_tokens": tokens * 2, "latency_ms": latency_ms}


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
