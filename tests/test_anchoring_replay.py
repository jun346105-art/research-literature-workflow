from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from litflow.anchoring_audit import AnchoringAuditError
from litflow.anchoring_replay import replay_anchoring_recovery
from litflow.llm.span_mapping import map_verbatim_span


def test_mapper_preserves_exact_and_original_source_span():
    text = "Exact source. method extracts useful\nevidence."
    exact = map_verbatim_span("Exact source.", text)
    normalized = map_verbatim_span("method extracts useful evidence.", text, normalized_matches=[(14, len(text))])
    assert exact.method == "exact_match"
    assert normalized.method == "normalized_whitespace_match"
    assert normalized.evidence_text == text[normalized.start : normalized.end]
    assert normalized.roundtrip_verified is True


def test_mapper_safe_mapping_and_rejections_are_conservative():
    recovered = map_verbatim_span("first sample wordcontinuation", "ﬁrst sample word-\ncontinuation")
    space = map_verbatim_span("wordcontinuation", "word- continuation")
    duplicate = map_verbatim_span("same phrase", "same phrase and same phrase")
    rewrite = map_verbatim_span("machine vision technology", "machine-vision based technology")
    assert recovered.status == "ok"
    assert recovered.evidence_text == "ﬁrst sample word-\ncontinuation"
    assert space.status == "not_found"
    assert duplicate.status == "ambiguous"
    assert rewrite.status == "not_found"


def test_replay_fails_closed_on_manifest_hash_mismatch_without_output(tmp_path):
    frozen, audit_dir, run = _replay_fixture(tmp_path)
    manifest = json.loads((audit_dir / "audit_manifest.json").read_text(encoding="utf-8"))
    manifest["frozen_manifest_sha256"] = "0" * 64
    (audit_dir / "audit_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AnchoringAuditError, match="frozen manifest SHA-256 mismatch"):
        replay_anchoring_recovery(audit_dir, frozen, [run], tmp_path / "result", repo_root=tmp_path)
    assert not (tmp_path / "result").exists()


def test_replay_tracks_existing_recovery_and_rejection(tmp_path):
    frozen, audit_dir, run = _replay_fixture(tmp_path)
    result = replay_anchoring_recovery(audit_dir, frozen, [run], tmp_path / "result", repo_root=tmp_path)
    assert result["existing_strict_substring_pass"] == 1
    assert result["new_recovery_roundtrip_pass"] == 1
    assert result["total_strict_substring_pass"] == 2
    assert result["still_rejected"] == 1


def test_replay_rejects_missing_audit_item_without_output(tmp_path):
    frozen, audit_dir, run = _replay_fixture(tmp_path)
    with (audit_dir / "items.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_audit_fields()); writer.writeheader()
    with pytest.raises(AnchoringAuditError, match="missing from audit items"):
        replay_anchoring_recovery(audit_dir, frozen, [run], tmp_path / "result", repo_root=tmp_path)
    assert not (tmp_path / "result").exists()


def test_replay_rejects_page_provenance_mismatch_without_output(tmp_path):
    frozen, audit_dir, run = _replay_fixture(tmp_path)
    bank_path = run / "papers" / "P1" / "proposed" / "evidence_candidate_bank.json"
    bank = json.loads(bank_path.read_text(encoding="utf-8")); bank["candidates"][0]["page_end"] = 9
    bank_path.write_text(json.dumps(bank), encoding="utf-8")
    manifest_path = audit_dir / "audit_manifest.json"; manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runs"][0]["candidate_bank_sha256"] = _sha(bank_path); manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AnchoringAuditError, match="page provenance"):
        replay_anchoring_recovery(audit_dir, frozen, [run], tmp_path / "result", repo_root=tmp_path)
    assert not (tmp_path / "result").exists()


def _replay_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"chunks": [{"chunk_id": "P1_chunk_0001", "text": "exact source; safe word-\ncontinuation", "page_start": 1, "page_end": 1}]}), encoding="utf-8")
    pdf = tmp_path / "paper.pdf"; pdf.write_bytes(b"pdf")
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps({"papers": [{"zotero_key": "P1", "source_clean_context_path": "context.json", "clean_context_sha256": _sha(context), "pdf_path": str(pdf), "pdf_sha256": _sha(pdf)}]}), encoding="utf-8")
    run = tmp_path / "run"; proposed = run / "papers" / "P1" / "proposed"; proposed.mkdir(parents=True)
    _write(run / "run_manifest.json", {"selected_paper_keys": ["P1"], "plan": {"selected_paper_keys": ["P1"], "manifest": "frozen.json"}})
    _write(run / "input_verification.json", {"verified": True, "papers": ["P1"]})
    common = {"status": "failed", "error_type": "evidence_anchor_not_found", "chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "evidence_type": "method", "claim": "claim", "message": "not found"}
    recovered = {**common, "quote_hint": "safe wordcontinuation"}
    rejected = {**common, "claim": "other claim", "quote_hint": "missing"}
    candidate = {"chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "evidence_type": "method", "evidence_text": "exact source", "anchoring_method": "exact_match"}
    _write(proposed / "evidence_candidate_bank.json", {"metadata": {"source": "context.json", "failed_count": 2}, "candidates": [candidate], "failures": [recovered, rejected]})
    _write(proposed / "candidate_report.json", {"failure_types": {"evidence_anchor_not_found": 2}})
    audit = tmp_path / "audit"; audit.mkdir()
    _write(audit / "audit_manifest.json", {"audit_rule_version": "span-traceability-audit-v1.1", "frozen_manifest_sha256": _sha(frozen), "runs": [{"paper_key": "P1", "run_name": "run", "candidate_bank_sha256": _sha(proposed / "evidence_candidate_bank.json")} ]})
    fields = _audit_fields()
    with (audit / "items.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore"); writer.writeheader()
        writer.writerow({"paper_key": "P1", "run_name": "run", **recovered, "original_anchoring_error": recovered["error_type"], "span_traceability_status": "normalized_unique_span_recoverable"})
        writer.writerow({"paper_key": "P1", "run_name": "run", **rejected, "original_anchoring_error": rejected["error_type"], "span_traceability_status": "no_verbatim_span"})
    return frozen, audit, run


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit_fields() -> list[str]:
    return ["paper_key", "run_name", "chunk_id", "page_start", "page_end", "evidence_type", "claim", "quote_hint", "original_anchoring_error", "span_traceability_status"]
