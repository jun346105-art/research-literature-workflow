from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import uuid
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Any


class EvaluationAggregateError(ValueError):
    pass


HUMAN_REVIEW_FIELDS = [
    "paper_key", "run_name", "review_id", "run_id", "zotero_key", "method",
    "evidence_index", "claim", "chunk_id", "page_start", "page_end", "evidence_text",
    "automatic_grounding_status", "automatic_failure_type", "support_label", "needs_revision",
    "acceptance", "reviewer_notes_raw", "reviewer_notes_integrity",
]


def aggregate_evaluation_pilot(
    run_dirs: list[Path],
    out_dir: Path,
    *,
    expected_reviewed_sha256: dict[str, str],
    command_args: list[str] | None = None,
    repo_root: Path | None = None,
    aggregator_git_commit_sha: str | None = None,
    input_price_cny_per_million_tokens: float = 1,
    output_price_cny_per_million_tokens: float = 2,
) -> dict[str, Any]:
    """Aggregate completed evaluation runs without constructing an LLM client."""
    if not run_dirs:
        raise EvaluationAggregateError("at least one --run-dir is required")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise EvaluationAggregateError(f"output directory already exists and is nonempty: {out_dir}")

    root = (repo_root or Path.cwd()).resolve()
    records, shared, inputs = _load_and_validate_runs(run_dirs, root, expected_reviewed_sha256)
    if out_dir.exists() and not out_dir.is_dir():
        raise EvaluationAggregateError(f"output path is not a directory: {out_dir}")

    summary = _build_summary(
        records,
        shared,
        input_price_cny_per_million_tokens,
        output_price_cny_per_million_tokens,
    )
    git_sha = aggregator_git_commit_sha or _git_commit_sha(root)
    temp_dir = out_dir.parent / f".{out_dir.name}.tmp-{uuid.uuid4().hex}"
    try:
        temp_dir.mkdir(parents=True)
        _write_outputs(temp_dir, summary, records)
        _write_reproduction_manifest(temp_dir, out_dir, root, inputs, command_args or [], git_sha)
        if out_dir.exists():
            out_dir.rmdir()
        temp_dir.replace(out_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    return summary


def nearest_rank_percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    return sorted(values)[math.ceil(percentile * len(values)) - 1]


def _load_and_validate_runs(
    run_dirs: list[Path], root: Path, expected_reviewed_sha256: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any], list[Path]]:
    records: list[dict[str, Any]] = []
    shared: dict[str, Any] | None = None
    input_paths: list[Path] = []
    seen_papers: set[str] = set()

    for run_dir in run_dirs:
        run_dir = run_dir.resolve()
        run_manifest_path = run_dir / "run_manifest.json"
        manifest = _load_json(run_manifest_path)
        plan = manifest.get("plan", {})
        selected = manifest.get("selected_paper_keys")
        planned_selected = plan.get("selected_paper_keys")
        if not isinstance(selected, list) or len(selected) != 1 or selected != planned_selected:
            raise EvaluationAggregateError(f"{run_dir}: selected_paper_keys must contain exactly one matching paper")
        paper_key = selected[0]
        if paper_key in seen_papers:
            raise EvaluationAggregateError(f"duplicate selected paper key: {paper_key}")
        seen_papers.add(paper_key)

        planned_papers = plan.get("papers", [])
        if len(planned_papers) != 1 or planned_papers[0].get("zotero_key") != paper_key:
            raise EvaluationAggregateError(f"{run_dir}: plan paper identity mismatch")
        planned_paper = planned_papers[0]
        frozen_path = _resolve_from_root(root, plan.get("manifest"), "frozen manifest")
        frozen = _load_json(frozen_path)
        frozen_paper = next((item for item in frozen.get("papers", []) if item.get("zotero_key") == paper_key), None)
        if frozen_paper is None:
            raise EvaluationAggregateError(f"{run_dir}: selected paper is missing from frozen manifest")
        research_path = _resolve_from_root(root, plan.get("research_context", {}).get("path"), "research context")
        context_path = _resolve_from_root(root, frozen_paper.get("source_clean_context_path"), "clean context")
        pdf_path = Path(frozen_paper.get("pdf_path", ""))
        if not pdf_path.is_file():
            raise EvaluationAggregateError(f"{run_dir}: frozen PDF is missing")
        if _sha256_file(context_path) != frozen_paper.get("clean_context_sha256"):
            raise EvaluationAggregateError(f"{run_dir}: clean context SHA-256 mismatch")
        if _sha256_file(pdf_path) != frozen_paper.get("pdf_sha256"):
            raise EvaluationAggregateError(f"{run_dir}: PDF SHA-256 mismatch")
        if _sha256_file(research_path) != plan.get("research_context", {}).get("sha256"):
            raise EvaluationAggregateError(f"{run_dir}: research context SHA-256 mismatch")

        baseline_path = run_dir / "papers" / paper_key / "baseline" / "metrics.json"
        proposed_path = run_dir / "papers" / paper_key / "proposed" / "metrics.json"
        bank_path = run_dir / "papers" / paper_key / "proposed" / "evidence_candidate_bank.json"
        candidate_report_path = run_dir / "papers" / paper_key / "proposed" / "candidate_report.json"
        final_note_path = run_dir / "papers" / paper_key / "proposed" / "final_note.json"
        call_metrics_path = run_dir / "call_metrics.json"
        reviewed_path = run_dir / "manual_claim_evidence_review_reviewed.csv"
        errors_path = run_dir / "errors.json"
        input_verification_path = run_dir / "input_verification.json"
        required = [
            run_manifest_path, baseline_path, proposed_path, bank_path, candidate_report_path,
            final_note_path, call_metrics_path, reviewed_path, errors_path, input_verification_path,
        ]
        if any(not path.is_file() for path in required):
            raise EvaluationAggregateError(f"{run_dir}: required run artifact is missing")
        expected_hash = expected_reviewed_sha256.get(paper_key)
        if expected_hash is None:
            raise EvaluationAggregateError(f"{run_dir}: expected reviewed CSV SHA-256 is missing for {paper_key}")
        if _sha256_file(reviewed_path) != expected_hash:
            raise EvaluationAggregateError(f"{run_dir}: reviewed CSV SHA-256 mismatch")

        config = {
            "frozen_manifest_sha256": _sha256_file(frozen_path),
            "git_commit_sha": manifest.get("git_commit_sha"),
            "model": manifest.get("model"),
            "temperature": manifest.get("temperature"),
            "request_config": manifest.get("request_config"),
            "context_window": manifest.get("context_window"),
            "research_context_sha256": plan.get("research_context", {}).get("sha256"),
            "prompt_versions": {
                "baseline": planned_paper.get("baseline_prompt_version"),
                "baseline_content_schema": planned_paper.get("baseline_content_schema_version"),
                "candidate": planned_paper.get("proposed_candidate_prompt_version"),
                "final": planned_paper.get("proposed_final_prompt_version"),
            },
        }
        if not config["git_commit_sha"] or not config["model"]:
            raise EvaluationAggregateError(f"{run_dir}: incomplete run configuration")
        if shared is None:
            shared = config
        elif config != shared:
            raise EvaluationAggregateError(f"{run_dir}: configuration mismatch across runs")

        verification = _load_json(input_verification_path)
        if verification.get("verified") is not True or verification.get("papers") != [paper_key]:
            raise EvaluationAggregateError(f"{run_dir}: input verification mismatch")
        reviewed_rows = _read_reviewed_csv(reviewed_path)
        calls = _load_json(call_metrics_path)
        if not isinstance(calls, list):
            raise EvaluationAggregateError(f"{run_dir}: call_metrics.json must contain a list")
        baseline = _load_json(baseline_path)
        proposed = _load_json(proposed_path)
        bank = _load_json(bank_path)
        candidate_report = _load_json(candidate_report_path)
        errors = _load_json(errors_path)
        if not isinstance(errors, list):
            raise EvaluationAggregateError(f"{run_dir}: errors.json must contain a list")

        summary_path = run_dir / "human_review_summary.json"
        input_paths.extend(required + [frozen_path, research_path, context_path, pdf_path])
        if summary_path.is_file():
            input_paths.append(summary_path)
        records.append(
            {
                "paper_key": paper_key,
                "run_name": run_dir.name,
                "run_dir": run_dir,
                "chunk_count": planned_paper.get("chunk_count", 0),
                "calls": calls,
                "baseline": baseline,
                "proposed": proposed,
                "bank": bank,
                "candidate_report": candidate_report,
                "errors": errors,
                "reviewed_rows": reviewed_rows,
                "artifact_paths": {
                    "run_manifest": run_manifest_path,
                    "call_metrics": call_metrics_path,
                    "baseline_metrics": baseline_path,
                    "proposed_metrics": proposed_path,
                    "candidate_bank": bank_path,
                    "candidate_report": candidate_report_path,
                    "final_note": final_note_path,
                    "reviewed_csv": reviewed_path,
                    "errors": errors_path,
                    "input_verification": input_verification_path,
                    "frozen_manifest": frozen_path,
                    "research_context": research_path,
                    "clean_context": context_path,
                    "pdf": pdf_path,
                },
            }
        )
    if set(expected_reviewed_sha256) != seen_papers:
        raise EvaluationAggregateError("expected reviewed CSV SHA-256 keys do not match supplied run papers")
    return records, shared or {}, list(dict.fromkeys(input_paths))


def _build_summary(
    records: list[dict[str, Any]], shared: dict[str, Any], input_price: float, output_price: float
) -> dict[str, Any]:
    per_paper = [_paper_metrics(record) for record in records]
    all_calls = [call for record in records for call in record["calls"]]
    calls_by_stage = {stage: [call for call in all_calls if call.get("stage") == stage] for stage in ("baseline_raw", "proposed_candidate_chunk", "proposed_final_note")}
    latency = {"overall": _latency_metrics(all_calls)}
    latency.update({stage: _latency_metrics(calls) for stage, calls in calls_by_stage.items()})
    candidate_total = sum(item["candidate"]["total"] for item in per_paper)
    anchored = sum(item["candidate"]["anchored"] for item in per_paper)
    covered = sum(item["candidate"]["covered_chunks"] for item in per_paper)
    chunk_count = sum(item["chunk_count"] for item in per_paper)
    human = _human_metrics(records)
    input_tokens = sum(_number(call.get("input_tokens")) for call in all_calls)
    output_tokens = sum(_number(call.get("output_tokens")) for call in all_calls)
    summary = {
        "scope": "Development pilot aggregation; not a held-out benchmark.",
        "consistency_validation": {"status": "passed", "shared_config": shared, "paper_count": len(records)},
        "metric_source_precedence": {
            "calls_usage_latency": "call_metrics.json",
            "baseline_grounding": "baseline/metrics.json",
            "proposed_grounding": "proposed/metrics.json",
            "candidate_metrics": "evidence_candidate_bank.json and candidate_report.json",
            "human_metrics": "reviewed CSV labels",
            "reviewer_notes": "non-authoritative qualitative field",
        },
        "per_paper": per_paper,
        "micro_aggregate": {
            "paper_count": len(records),
            "chunk_count": chunk_count,
            "calls": {"baseline": len(calls_by_stage["baseline_raw"]), "candidate": len(calls_by_stage["proposed_candidate_chunk"]), "final": len(calls_by_stage["proposed_final_note"]), "total": len(all_calls)},
            "retry_count": sum(call.get("attempt", 1) > 1 for call in all_calls),
            "runner_error_count": sum(len(record["errors"]) for record in records),
            "schema_failures": {
                "baseline_raw_json": sum(not item["baseline"]["raw_json_parse_valid"] for item in per_paper),
                "baseline_content": sum(not item["baseline"]["content_schema_valid"] for item in per_paper),
                "baseline_scoring_view": sum(not item["baseline"]["scoring_view_valid"] for item in per_paper),
                "proposed_final": sum(not item["proposed_final"]["schema_valid"] for item in per_paper),
            },
            "provider_usage_statuses": dict(Counter(str(call.get("usage_status")) for call in all_calls)),
            "tokens": {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": sum(_number(call.get("total_tokens")) for call in all_calls)},
            "latency_ms": latency,
            "baseline": _baseline_micro(per_paper),
            "proposed_candidate": {
                "total": candidate_total,
                "anchored": anchored,
                "failed": sum(item["candidate"]["failed"] for item in per_paper),
                "anchor_rate": _ratio(anchored, candidate_total),
                "chunk_coverage_micro": _ratio(covered, chunk_count),
                "anchoring_methods": dict(sum((Counter(item["candidate"]["anchoring_methods"]) for item in per_paper), Counter())),
                "failure_types": dict(sum((Counter(item["candidate"]["failure_types"]) for item in per_paper), Counter())),
            },
            "proposed_final": _proposed_micro(per_paper),
        },
        "human_review_aggregate": human,
        "reviewer_notes_integrity": _notes_integrity(records),
        "cost": {
            "input_price_cny_per_million_tokens": input_price,
            "output_price_cny_per_million_tokens": output_price,
            "reference_estimated_cost_cny": round(input_tokens / 1_000_000 * input_price + output_tokens / 1_000_000 * output_price, 6),
            "note": "Reference estimate only; not a provider invoice and does not alter source artifacts.",
        },
        "known_limitations": _known_limitations(records),
    }
    return summary


def _paper_metrics(record: dict[str, Any]) -> dict[str, Any]:
    calls = record["calls"]
    by_stage = {stage: [call for call in calls if call.get("stage") == stage] for stage in ("baseline_raw", "proposed_candidate_chunk", "proposed_final_note")}
    baseline = record["baseline"]
    proposed = record["proposed"]
    candidates = record["bank"].get("candidates", [])
    failures = record["bank"].get("failures", [])
    methods = Counter(item.get("anchoring_method") for item in candidates if item.get("anchoring_method"))
    failure_types = Counter(item.get("error_type", "unknown") for item in failures)
    report_methods = record["candidate_report"].get("anchoring_methods")
    report_failure_types = record["candidate_report"].get("failure_types")
    if isinstance(report_methods, dict):
        methods = Counter(report_methods)
    if isinstance(report_failure_types, dict):
        failure_types = Counter(report_failure_types)
    return {
        "paper_key": record["paper_key"], "run_name": record["run_name"], "chunk_count": record["chunk_count"],
        "calls": {"baseline": len(by_stage["baseline_raw"]), "candidate": len(by_stage["proposed_candidate_chunk"]), "final": len(by_stage["proposed_final_note"]), "total": len(calls)},
        "retry_count": sum(call.get("attempt", 1) > 1 for call in calls),
        "runner_error_count": len(record["errors"]),
        "usage_statuses": dict(Counter(str(call.get("usage_status")) for call in calls)),
        "tokens": {"input_tokens": sum(_number(call.get("input_tokens")) for call in calls), "output_tokens": sum(_number(call.get("output_tokens")) for call in calls), "total_tokens": sum(_number(call.get("total_tokens")) for call in calls)},
        "latency_ms": {stage: sum(_number(call.get("latency_ms")) for call in values) for stage, values in by_stage.items()},
        "baseline": {
            "evidence_count": baseline.get("evidence_links_count", 0), "strict_pass": baseline.get("exact_grounding_pass_count", 0), "strict_fail": baseline.get("exact_grounding_failure_count", 0),
            "evidence_text_not_found": baseline.get("evidence_text_not_found_count", 0), "page_range_mismatch": baseline.get("page_range_mismatch_count", 0), "chunk_id_not_found": baseline.get("chunk_id_not_found_count", 0),
            "raw_json_parse_valid": bool(baseline.get("raw_json_parse_valid")), "content_schema_valid": bool(baseline.get("baseline_content_schema_valid")), "scoring_view_valid": bool(baseline.get("baseline_scoring_view_valid")),
        },
        "candidate": {"total": len(candidates) + len(failures), "anchored": len(candidates), "failed": len(failures), "covered_chunks": len({item.get("chunk_id") for item in candidates if item.get("chunk_id")}), "anchoring_methods": dict(methods), "failure_types": dict(failure_types)},
        "proposed_final": {"evidence_count": proposed.get("final_selected_evidence_count", 0), "strict_pass": proposed.get("exact_grounding_pass_count", 0), "strict_fail": proposed.get("exact_grounding_failure_count", 0), "schema_valid": bool(proposed.get("schema_valid"))},
        "artifact_paths": {name: str(path) for name, path in record["artifact_paths"].items()},
    }


def _baseline_micro(records: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {"evidence_count": "evidence_count", "strict_pass": "strict_pass", "strict_fail": "strict_fail", "evidence_text_not_found": "evidence_text_not_found", "page_range_mismatch": "page_range_mismatch", "chunk_id_not_found": "chunk_id_not_found"}
    result = {name: sum(item["baseline"][field] for item in records) for name, field in fields.items()}
    count = len(records)
    result.update({"raw_json_parse_valid": _ratio(sum(item["baseline"]["raw_json_parse_valid"] for item in records), count), "content_schema_valid": _ratio(sum(item["baseline"]["content_schema_valid"] for item in records), count), "scoring_view_valid": _ratio(sum(item["baseline"]["scoring_view_valid"] for item in records), count)})
    return result


def _proposed_micro(records: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(records)
    return {"evidence_count": sum(item["proposed_final"]["evidence_count"] for item in records), "strict_pass": sum(item["proposed_final"]["strict_pass"] for item in records), "strict_fail": sum(item["proposed_final"]["strict_fail"] for item in records), "schema_valid": _ratio(sum(item["proposed_final"]["schema_valid"] for item in records), count)}


def _human_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for method in ("baseline", "proposed"):
        rows = [row for record in records for row in record["reviewed_rows"] if row.get("method") == method]
        count = len(rows)
        result[method] = {
            "sample_count": count,
            "supported": _ratio(sum(row["support_label"] == "supported" for row in rows), count),
            "partially_supported": _ratio(sum(row["support_label"] == "partially_supported" for row in rows), count),
            "unsupported": _ratio(sum(row["support_label"] == "unsupported" for row in rows), count),
            "supported_plus_partially": _ratio(sum(row["support_label"] in {"supported", "partially_supported"} for row in rows), count),
            "accept": _ratio(sum(row["acceptance"] == "accept" for row in rows), count),
            "revise": _ratio(sum(row["acceptance"] == "revise" for row in rows), count),
            "reject": _ratio(sum(row["acceptance"] == "reject" for row in rows), count),
            "automatic_grounding_x_human_support": dict(Counter(f"{row['automatic_grounding_status']}|{row['support_label']}" for row in rows)),
        }
    return result


def _notes_integrity(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(_reviewer_notes_integrity(row.get("reviewer_notes", "")) for record in records for row in record["reviewed_rows"]))


def _reviewer_notes_integrity(note: str) -> str:
    meaningful = [character for character in note if not character.isspace()]
    if not meaningful:
        return "missing"
    question_count = meaningful.count("?")
    if question_count / len(meaningful) >= 0.5 or (question_count and all(ord(character) < 128 for character in meaningful)):
        return "legacy_encoding_lost"
    return "ok"


def _known_limitations(records: list[dict[str, Any]]) -> list[str]:
    limits = [
        "Development pilot only; not a held-out benchmark.",
        "Baseline and Proposed claims are not paired claim-by-claim.",
        "Human labels are project-author review with AI-assisted translation, not independent blinded expert annotation.",
        "Exact grounding does not establish semantic correctness.",
        "Candidate chunk coverage does not equal retrieval recall.",
    ]
    for record in records:
        summary_path = record["run_dir"] / "human_review_summary.json"
        if summary_path.is_file():
            limits.extend(_load_json(summary_path).get("known_observations", []))
    return list(dict.fromkeys(limits))


def _write_outputs(out_dir: Path, summary: dict[str, Any], records: list[dict[str, Any]]) -> None:
    _atomic_write(out_dir / "aggregate_summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(out_dir / "aggregate_summary.md", _summary_markdown(summary))
    _write_csv(out_dir / "per_paper_metrics.csv", [_per_paper_row(item) for item in summary["per_paper"]], list(_per_paper_row(summary["per_paper"][0])))
    rows = []
    for record in records:
        for index, row in enumerate(record["reviewed_rows"], 1):
            rows.append({"paper_key": record["paper_key"], "run_name": record["run_name"], "review_id": f"{record['paper_key']}-{index:03d}", "run_id": row.get("run_id", ""), "zotero_key": row.get("zotero_key", ""), "method": row.get("method", ""), "evidence_index": row.get("evidence_index", ""), "claim": row.get("claim", ""), "chunk_id": row.get("chunk_id", ""), "page_start": row.get("page_start", ""), "page_end": row.get("page_end", ""), "evidence_text": row.get("evidence_text", ""), "automatic_grounding_status": row.get("automatic_grounding_status", ""), "automatic_failure_type": row.get("automatic_failure_type", ""), "support_label": row.get("support_label", ""), "needs_revision": row.get("needs_revision", ""), "acceptance": row.get("acceptance", ""), "reviewer_notes_raw": row.get("reviewer_notes", ""), "reviewer_notes_integrity": _reviewer_notes_integrity(row.get("reviewer_notes", ""))})
    _write_csv(out_dir / "human_review_aggregate.csv", rows, HUMAN_REVIEW_FIELDS)
    failures = []
    for record in records:
        for failure in record["bank"].get("failures", []):
            failures.append({"paper_key": record["paper_key"], "run_name": record["run_name"], **failure})
    fields = ["paper_key", "run_name", "status", "error_type", "chunk_id", "page_start", "page_end", "evidence_type", "claim", "quote_hint", "message"]
    _write_csv(out_dir / "anchoring_failure_inventory.csv", failures, fields)


def _write_reproduction_manifest(
    write_dir: Path,
    final_out_dir: Path,
    root: Path,
    inputs: list[Path],
    command_args: list[str],
    git_sha: str,
) -> None:
    output_names = ("aggregate_summary.json", "aggregate_summary.md", "per_paper_metrics.csv", "human_review_aggregate.csv", "anchoring_failure_inventory.csv")
    module_path = Path(__file__).resolve()
    manifest = {
        "aggregator_git_commit_sha": git_sha,
        "aggregator_module_path": _path_record(module_path, root),
        "aggregator_module_sha256": _sha256_file(module_path),
        "replay_command": command_args,
        "python_version": sys.version,
        "inputs": [_path_record(path, root) for path in inputs],
        "outputs": [
            _path_record_with_display_path(write_dir / name, final_out_dir / name, root)
            for name in output_names
        ],
        "percentile_algorithm": "nearest-rank: sorted_values[ceil(p*n)-1]",
        "cost_formula": "input_tokens * input_price_per_million / 1000000 + output_tokens * output_price_per_million / 1000000",
        "reviewer_notes_integrity_policy": "missing for blank; legacy_encoding_lost for question-majority or ASCII question residue; otherwise ok.",
        "self_hash_note": "The reproduction manifest does not embed its own SHA-256 because that would be circular.",
    }
    _atomic_write(write_dir / "reproduction_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def _summary_markdown(summary: dict[str, Any]) -> str:
    micro = summary["micro_aggregate"]
    human = summary["human_review_aggregate"]
    lines = ["# Evaluation Aggregate Summary", "", f"- Papers: {micro['paper_count']}", f"- Chunks: {micro['chunk_count']}", f"- Calls: {micro['calls']['total']} (baseline {micro['calls']['baseline']}, candidate {micro['calls']['candidate']}, final {micro['calls']['final']})", f"- Reference estimated cost (CNY): {summary['cost']['reference_estimated_cost_cny']:.6f}", "", "## Human Review", "", "| Method | Supported | Partially | Unsupported | Accept | Revise | Reject |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for method in ("baseline", "proposed"):
        item = human[method]
        lines.append(f"| {method} | {_format_ratio(item['supported'])} | {_format_ratio(item['partially_supported'])} | {_format_ratio(item['unsupported'])} | {_format_ratio(item['accept'])} | {_format_ratio(item['revise'])} | {_format_ratio(item['reject'])} |")
    lines.extend(["", "## Reviewer Notes Integrity", ""] + [f"- {status}: {count}" for status, count in sorted(summary["reviewer_notes_integrity"].items())])
    return "\n".join(lines) + "\n"


def _per_paper_row(item: dict[str, Any]) -> dict[str, Any]:
    return {"paper_key": item["paper_key"], "run_name": item["run_name"], "chunk_count": item["chunk_count"], "baseline_calls": item["calls"]["baseline"], "candidate_calls": item["calls"]["candidate"], "final_calls": item["calls"]["final"], "total_calls": item["calls"]["total"], "retry_count": item["retry_count"], "input_tokens": item["tokens"]["input_tokens"], "output_tokens": item["tokens"]["output_tokens"], "total_tokens": item["tokens"]["total_tokens"], "baseline_evidence": item["baseline"]["evidence_count"], "baseline_strict_pass": item["baseline"]["strict_pass"], "baseline_strict_fail": item["baseline"]["strict_fail"], "candidate_total": item["candidate"]["total"], "candidate_anchored": item["candidate"]["anchored"], "candidate_failed": item["candidate"]["failed"], "candidate_covered_chunks": item["candidate"]["covered_chunks"], "proposed_evidence": item["proposed_final"]["evidence_count"], "proposed_strict_pass": item["proposed_final"]["strict_pass"], "proposed_strict_fail": item["proposed_final"]["strict_fail"]}


def _read_reviewed_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise EvaluationAggregateError(f"{path}: reviewed CSV has duplicate or missing headers")
        rows = list(reader)
    required = ("support_label", "needs_revision", "acceptance", "reviewer_notes")
    if not rows or any(not row.get(field, "").strip() for row in rows for field in required):
        raise EvaluationAggregateError(f"{path}: reviewed CSV has incomplete human review fields")
    return rows


def _latency_metrics(calls: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_number(call.get("latency_ms")) for call in calls if call.get("latency_ms") is not None]
    return {"sample_count": len(values), "total_ms": sum(values), "p50_ms": nearest_rank_percentile(values, 0.5), "p95_ms": nearest_rank_percentile(values, 0.95)}


def _ratio(numerator: int | bool, denominator: int) -> dict[str, Any]:
    value = int(numerator)
    return {"numerator": value, "denominator": denominator, "rate": value / denominator if denominator else None}


def _number(value: Any) -> float | int:
    return value if isinstance(value, (int, float)) else 0


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise EvaluationAggregateError(f"required file is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _resolve_from_root(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise EvaluationAggregateError(f"{label} path is missing")
    path = Path(value)
    resolved = path if path.is_absolute() else root / path
    if not resolved.is_file():
        raise EvaluationAggregateError(f"{label} is missing: {resolved}")
    return resolved


def _path_record(path: Path, root: Path) -> dict[str, str]:
    try:
        relative = os.path.relpath(path.resolve(), root.resolve()).replace("\\", "/")
        return {"path": relative, "path_type": "relative_to_repo", "sha256": _sha256_file(path)}
    except ValueError:
        return {"path": str(path.resolve()), "path_type": "private_local_path", "sha256": _sha256_file(path)}


def _path_record_with_display_path(source: Path, display: Path, root: Path) -> dict[str, str]:
    record = _path_record(source, root)
    try:
        record["path"] = os.path.relpath(display.resolve(), root.resolve()).replace("\\", "/")
        record["path_type"] = "relative_to_repo"
    except ValueError:
        record["path"] = str(display.resolve())
        record["path_type"] = "private_local_path"
    return record


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    _atomic_write(path, stream.getvalue())


def _atomic_write(path: Path, text: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="")
    temp.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_commit_sha(root: Path) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    if result.returncode:
        raise EvaluationAggregateError("cannot determine aggregator Git commit SHA")
    return result.stdout.strip()


def _format_ratio(item: dict[str, Any]) -> str:
    return f"{item['numerator']} / {item['denominator']}"
