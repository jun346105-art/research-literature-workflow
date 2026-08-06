from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from litflow.anchoring_audit import AnchoringAuditError, ITEM_FIELDS, _audit_item, audit_anchoring_failures


def test_safe_mapping_handles_utf8_extraction_artifacts():
    row = _row("P1", "run", "P1_chunk_0001", "The first sample has a softhyphen and zerowidth word", "evidence_anchor_not_found")
    context = {"chunks": [{"chunk_id": "P1_chunk_0001", "text": "The ﬁrst sample has a soft\u00adhyphen and zero\u200bwidth word.", "page_start": 1, "page_end": 1}]}
    item = _audit_item(row, context, 1)
    assert item["span_traceability_status"] == "normalized_unique_span_recoverable"
    assert item["verbatim_eligibility"] == "eligible_after_safe_span_mapping"
    assert item["mapped_span_char_count"] > 0
    assert item["mapping_normalization_profile"] == "safe_nfkc_alnum_v1"
    assert item["roundtrip_verified"] is True


def test_dehyphenation_requires_a_real_line_break():
    space = _audit_item(_row("P1", "run", "P1_chunk_0001", "wordcontinuation", "evidence_anchor_not_found"), {"chunks": [{"chunk_id": "P1_chunk_0001", "text": "word- continuation", "page_start": 1, "page_end": 1}]}, 1)
    newline = _audit_item(_row("P1", "run", "P1_chunk_0001", "wordcontinuation", "evidence_anchor_not_found"), {"chunks": [{"chunk_id": "P1_chunk_0001", "text": "word-\ncontinuation", "page_start": 1, "page_end": 1}]}, 2)
    assert space["span_traceability_status"] != "normalized_unique_span_recoverable"
    assert newline["span_traceability_status"] == "normalized_unique_span_recoverable"
    assert "linebreak_dehyphenation" in newline["local_mapping_features"]


def test_similarity_and_unrelated_chunk_noise_do_not_change_provenance_or_features():
    item = _audit_item(_row("P1", "run", "P1_chunk_0001", "alpha beta gamma", "evidence_anchor_not_found"), {"chunks": [{"chunk_id": "P1_chunk_0001", "text": "declared alpha delta", "page_start": 1, "page_end": 1}, {"chunk_id": "P1_chunk_0002", "text": "alpha beta extra gamma\x00 ﬁ", "page_start": 2, "page_end": 2}]}, 1)
    assert item["span_traceability_status"] != "wrong_provenance"
    assert item["local_mapping_features"] == ""


def test_duplicate_and_wrong_provenance_stay_ineligible():
    duplicate = _audit_item(_row("P1", "run", "P1_chunk_0001", "repeat phrase", "evidence_anchor_ambiguous"), {"chunks": [{"chunk_id": "P1_chunk_0001", "text": "repeat phrase and repeat phrase", "page_start": 1, "page_end": 1}]}, 1)
    other = _audit_item(_row("P1", "run", "P1_chunk_0001", "source only elsewhere", "evidence_anchor_not_found"), {"chunks": [{"chunk_id": "P1_chunk_0001", "text": "declared chunk", "page_start": 1, "page_end": 1}, {"chunk_id": "P1_chunk_0002", "text": "source only elsewhere", "page_start": 2, "page_end": 2}]}, 2)
    assert duplicate["verbatim_eligibility"] == "not_eligible_ambiguous"
    assert other["span_traceability_status"] == "wrong_provenance"
    assert other["semantic_support_status"] == "unreviewed"


def test_non_contiguous_and_rewrite_are_not_accepted_as_quotes():
    non_contiguous = _audit_item(_row("P1", "run", "P1_chunk_0001", "alpha beta gamma delta epsilon zeta eta theta", "evidence_anchor_not_found"), {"chunks": [{"chunk_id": "P1_chunk_0001", "text": "alpha beta gamma delta inserted content epsilon zeta eta theta", "page_start": 1, "page_end": 1}]}, 1)
    rewrite = _audit_item(_row("P1", "run", "P1_chunk_0001", "The method applies machine vision technology", "evidence_anchor_not_found"), {"chunks": [{"chunk_id": "P1_chunk_0001", "text": "The method is to apply machine vision technology.", "page_start": 1, "page_end": 1}]}, 2)
    assert non_contiguous["verbatim_eligibility"] == "not_eligible_non_contiguous"
    assert rewrite["verbatim_eligibility"] == "not_eligible_model_rewrite"
    assert rewrite["semantic_support_status"] == "unreviewed"


def test_audit_is_fail_closed_and_writes_stable_utf8_output(tmp_path):
    inventory, frozen, run_dir = _make_run(tmp_path)
    out_dir = tmp_path / "audit"
    report = audit_anchoring_failures(inventory, frozen, [run_dir], out_dir, repo_root=tmp_path)
    with (out_dir / "items.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ITEM_FIELDS
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["semantic_support_status"] == "unreviewed"
    assert report["total_failures"] == 1

    context = json.loads((tmp_path / "context.json").read_text(encoding="utf-8"))
    context["chunks"][0]["text"] = "changed"
    (tmp_path / "context.json").write_text(json.dumps(context), encoding="utf-8")
    with pytest.raises(AnchoringAuditError, match="clean context SHA-256 mismatch"):
        audit_anchoring_failures(inventory, frozen, [run_dir], tmp_path / "audit-failed", repo_root=tmp_path)
    assert not (tmp_path / "audit-failed").exists()


def test_audit_cleans_temporary_directory_after_write_error(tmp_path, monkeypatch):
    inventory, frozen, run_dir = _make_run(tmp_path)
    out_dir = tmp_path / "audit"
    monkeypatch.setattr("litflow.anchoring_audit._write_outputs", lambda *_args: (_ for _ in ()).throw(OSError("write failed")))
    with pytest.raises(OSError, match="write failed"):
        audit_anchoring_failures(inventory, frozen, [run_dir], out_dir, repo_root=tmp_path)
    assert not out_dir.exists()
    assert not list(tmp_path.glob(".audit.tmp-*"))


def _make_run(tmp_path: Path) -> tuple[Path, Path, Path]:
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"chunks": [{"chunk_id": "P1_chunk_0001", "text": "source sentence", "page_start": 1, "page_end": 1}]}), encoding="utf-8")
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"pdf")
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps({"papers": [{"zotero_key": "P1", "source_clean_context_path": "context.json", "clean_context_sha256": _sha(context), "pdf_path": str(pdf), "pdf_sha256": _sha(pdf)}]}), encoding="utf-8")
    run = tmp_path / "run"
    (run / "papers" / "P1" / "proposed").mkdir(parents=True)
    _write_json(run / "run_manifest.json", {"selected_paper_keys": ["P1"], "plan": {"selected_paper_keys": ["P1"], "manifest": "frozen.json"}})
    _write_json(run / "input_verification.json", {"verified": True, "papers": ["P1"]})
    failure = {"status": "failed", "error_type": "evidence_anchor_not_found", "chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "evidence_type": "method", "claim": "中文 claim", "quote_hint": "source sentence", "message": "not found"}
    _write_json(run / "papers" / "P1" / "proposed" / "evidence_candidate_bank.json", {"metadata": {"failed_count": 1, "source": "context.json"}, "failures": [failure]})
    _write_json(run / "papers" / "P1" / "proposed" / "candidate_report.json", {"failure_types": {"evidence_anchor_not_found": 1}})
    inventory = tmp_path / "inventory.csv"
    with inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["paper_key", "run_name", "status", "error_type", "chunk_id", "page_start", "page_end", "evidence_type", "claim", "quote_hint", "message"])
        writer.writeheader()
        writer.writerow({"paper_key": "P1", "run_name": "run", **failure})
    return inventory, frozen, run


def _row(paper: str, run: str, chunk: str, hint: str, error: str) -> dict[str, str]:
    return {"paper_key": paper, "run_name": run, "status": "failed", "error_type": error, "chunk_id": chunk, "page_start": "1", "page_end": "1", "evidence_type": "method", "claim": "claim", "quote_hint": hint, "message": "failed"}


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
