from __future__ import annotations

import csv
import hashlib
import json
import shutil
import uuid
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Any

from litflow.anchoring_audit import (
    AUDIT_RULE_VERSION, AnchoringAuditError, _git_state, _load_and_validate_runs, _load_json,
    _path_record, _sha256_file,
)
from litflow.llm.span_mapping import map_verbatim_span


REPLAY_RULE_VERSION = "offline-safe-span-recovery-replay-v1"
ITEM_FIELDS = [
    "paper_key", "run_name", "historical_status", "candidate_index", "chunk_id", "page_start", "page_end",
    "evidence_type", "replay_status", "method", "error_type", "roundtrip_verified", "evidence_text_sha256",
]


def replay_anchoring_recovery(
    audit_dir: Path, frozen_manifest_path: Path, run_dirs: list[Path], out_dir: Path, *, repo_root: Path | None = None
) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise AnchoringAuditError(f"output directory already exists and is nonempty: {out_dir}")
    if out_dir.exists() and not out_dir.is_dir():
        raise AnchoringAuditError(f"output path is not a directory: {out_dir}")
    root = (repo_root or Path.cwd()).resolve()
    audit_manifest = _load_json(audit_dir / "audit_manifest.json")
    if audit_manifest.get("audit_rule_version") != AUDIT_RULE_VERSION:
        raise AnchoringAuditError("audit rule version is not the committed v1.1 rule")
    frozen = _load_json(frozen_manifest_path)
    if audit_manifest.get("frozen_manifest_sha256") != _sha256_file(frozen_manifest_path):
        raise AnchoringAuditError("audit manifest frozen manifest SHA-256 mismatch")
    audit_rows = _read_audit_rows(audit_dir / "items.csv")
    records, input_paths = _load_and_validate_runs(run_dirs, root, frozen_manifest_path, frozen)
    by_key = {(item["paper_key"], item["run_name"]): item for item in audit_manifest.get("runs", [])}
    for record in records:
        audit_run = by_key.get((record["paper_key"], record["run_name"]))
        if not audit_run or audit_run.get("candidate_bank_sha256") != _sha256_file(record["paths"]["candidate_bank"]):
            raise AnchoringAuditError("audit manifest candidate bank SHA-256 mismatch")

    items: list[dict[str, Any]] = []
    for record in records:
        chunks = {chunk.get("chunk_id"): chunk for chunk in record["context"].get("chunks", [])}
        for index, candidate in enumerate(record["bank"].get("candidates", []), 1):
            chunk = chunks.get(candidate.get("chunk_id"))
            _validate_provenance(candidate, chunk)
            text = chunk.get("text") if chunk else ""
            evidence = candidate.get("evidence_text") or ""
            valid = bool(chunk and evidence and evidence in text)
            items.append(_item(record, candidate, "historical_anchored", index, "existing_valid" if valid else "existing_invalid", candidate.get("anchoring_method", ""), "" if valid else "strict_substring_failed", "not_applicable", evidence))
        for index, candidate in enumerate(record["bank"].get("failures", []), 1):
            chunk = chunks.get(candidate.get("chunk_id"))
            _validate_provenance(candidate, chunk)
            text = chunk.get("text") if chunk else ""
            failure_key = _failure_key(record, candidate)
            if failure_key not in audit_rows:
                raise AnchoringAuditError("candidate bank failure is missing from audit items")
            audit_status = audit_rows.pop(failure_key)
            mapping = map_verbatim_span(candidate.get("quote_hint") or "", text) if chunk else None
            if mapping and mapping.status == "ok":
                status, method, error, evidence = "newly_recovered", mapping.method, "", mapping.evidence_text
            else:
                status = "still_rejected"
                method = ""
                error = audit_status
                evidence = ""
            items.append(_item(record, candidate, "historical_failed", index, status, method, error, bool(mapping and mapping.roundtrip_verified), evidence))

    summary = _summary(items)
    if audit_rows:
        raise AnchoringAuditError("audit items do not match supplied candidate bank failures")
    manifest = {
        "replay_rule_version": REPLAY_RULE_VERSION, "span_mapping_profile": "safe_nfkc_alnum_v1",
        "git": _git_state(root), "audit_manifest_sha256": _sha256_file(audit_dir / "audit_manifest.json"),
        "frozen_manifest_sha256": _sha256_file(frozen_manifest_path),
        "inputs": [_path_record(path, root, redact=path.suffix.lower() == ".pdf") for path in input_paths],
        "output_policy": "temporary directory followed by atomic rename; output must be absent or empty",
    }
    temp_dir = out_dir.parent / f".{out_dir.name}.tmp-{uuid.uuid4().hex}"
    try:
        temp_dir.mkdir(parents=True)
        _write(temp_dir, summary, items, manifest)
        if out_dir.exists():
            out_dir.rmdir()
        temp_dir.replace(out_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return summary


def _item(record: dict[str, Any], candidate: dict[str, Any], historical: str, index: int, status: str, method: str, error: str, roundtrip: bool | str, evidence: str) -> dict[str, Any]:
    return {"paper_key": record["paper_key"], "run_name": record["run_name"], "historical_status": historical, "candidate_index": index,
            "chunk_id": candidate.get("chunk_id", ""), "page_start": candidate.get("page_start", ""), "page_end": candidate.get("page_end", ""),
            "evidence_type": candidate.get("evidence_type", ""), "replay_status": status, "method": method, "error_type": error,
            "roundtrip_verified": roundtrip, "evidence_text_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest() if evidence else ""}


def _validate_provenance(candidate: dict[str, Any], chunk: dict[str, Any] | None) -> None:
    if chunk is None:
        raise AnchoringAuditError("candidate chunk_id is missing from clean context")
    if candidate.get("page_start") != chunk.get("page_start") or candidate.get("page_end") != chunk.get("page_end"):
        raise AnchoringAuditError("candidate page provenance does not match declared chunk")


def _read_audit_rows(path: Path) -> dict[tuple[str, ...], str]:
    if not path.is_file():
        raise AnchoringAuditError("audit items.csv is missing")
    result: dict[tuple[str, ...], str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = tuple(row.get(name, "") for name in ("paper_key", "run_name", "chunk_id", "page_start", "page_end", "evidence_type", "claim", "quote_hint", "original_anchoring_error"))
            if key in result:
                raise AnchoringAuditError("audit items contain duplicate candidate failure identities")
            result[key] = row.get("span_traceability_status", "unknown")
    return result


def _failure_key(record: dict[str, Any], candidate: dict[str, Any]) -> tuple[str, ...]:
    return (record["paper_key"], record["run_name"], *(str(candidate.get(name, "")) for name in ("chunk_id", "page_start", "page_end", "evidence_type", "claim", "quote_hint", "error_type")))


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(item["replay_status"] for item in items)
    methods = Counter(item["method"] for item in items if item["method"])
    by_paper = {paper: dict(Counter(item["replay_status"] for item in items if item["paper_key"] == paper)) for paper in sorted({item["paper_key"] for item in items})}
    return {"metadata": {"replay_rule_version": REPLAY_RULE_VERSION, "scope": "offline replay only; no LLM calls or historical artifact changes"},
            "historical_anchored_count": sum(item["historical_status"] == "historical_anchored" for item in items),
            "historical_failed_count": sum(item["historical_status"] == "historical_failed" for item in items),
            "existing_anchored_still_valid": counts["existing_valid"], "newly_recovered": counts["newly_recovered"],
            "still_rejected": counts["still_rejected"], "methods": dict(methods),
            "existing_strict_substring_pass": counts["existing_valid"],
            "new_recovery_roundtrip_pass": sum(item["replay_status"] == "newly_recovered" and item["roundtrip_verified"] is True for item in items),
            "total_strict_substring_pass": counts["existing_valid"] + counts["newly_recovered"],
            "rejection_reasons": dict(Counter(item["error_type"] for item in items if item["replay_status"] == "still_rejected")), "by_paper": by_paper}


def _write(out_dir: Path, summary: dict[str, Any], items: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    (out_dir / "replay_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "replay_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ITEM_FIELDS, extrasaction="ignore")
    writer.writeheader(); writer.writerows(items)
    (out_dir / "replay_items.csv").write_text(stream.getvalue(), encoding="utf-8", newline="")
    lines = ["# Offline Safe Span Recovery Replay", "", f"- Historical anchored: {summary['historical_anchored_count']}", f"- Historical failed: {summary['historical_failed_count']}", f"- Existing strict substring pass: {summary['existing_strict_substring_pass']}", f"- New recovery round-trip pass: {summary['new_recovery_roundtrip_pass']}", f"- Total strict substring pass: {summary['total_strict_substring_pass']}", f"- Still rejected: {summary['still_rejected']}", "", "No LLM calls were made and no historical artifact was modified."]
    (out_dir / "replay_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
