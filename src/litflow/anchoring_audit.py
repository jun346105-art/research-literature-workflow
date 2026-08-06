from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import unicodedata
import uuid
from collections import Counter
from difflib import SequenceMatcher
from io import StringIO
from pathlib import Path
from typing import Any

from litflow.llm.structured_reader import _normalized_span_matches


class AnchoringAuditError(ValueError):
    pass


AUDIT_RULE_VERSION = "span-traceability-audit-v1.1"
INVENTORY_FIELDS = [
    "paper_key", "run_name", "status", "error_type", "chunk_id", "page_start", "page_end",
    "evidence_type", "claim", "quote_hint", "message",
]
ITEM_FIELDS = [
    "paper_key", "run_name", "candidate_failure_index", "chunk_id", "page_start", "page_end",
    "evidence_type", "claim", "quote_hint", "original_anchoring_error",
    "span_traceability_status", "semantic_support_status", "verbatim_eligibility",
    "suggested_primary_cause", "reviewed_primary_cause", "secondary_flags",
    "suggestion_confidence", "declared_exact_occurrences", "current_normalized_occurrences",
    "safe_normalized_occurrences", "other_chunk_matches", "adjacent_chunk_matches",
    "mapped_span_start", "mapped_span_end", "mapped_span_char_count", "mapped_span_sha256",
    "mapping_normalization_profile", "local_mapping_features", "roundtrip_verified", "diagnostic_similarity",
]


def audit_anchoring_failures(
    failure_inventory_path: Path,
    frozen_manifest_path: Path,
    run_dirs: list[Path],
    out_dir: Path,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Audit historical candidate failures without changing production anchoring."""
    if not run_dirs:
        raise AnchoringAuditError("at least one --run-dir is required")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise AnchoringAuditError(f"output directory already exists and is nonempty: {out_dir}")
    if out_dir.exists() and not out_dir.is_dir():
        raise AnchoringAuditError(f"output path is not a directory: {out_dir}")

    root = (repo_root or Path.cwd()).resolve()
    inventory_rows = _read_inventory(failure_inventory_path)
    frozen = _load_json(frozen_manifest_path)
    records, input_paths = _load_and_validate_runs(run_dirs, root, frozen_manifest_path, frozen)
    expected_rows = _failure_rows_from_banks(records)
    if Counter(_row_key(row) for row in inventory_rows) != Counter(_row_key(row) for row in expected_rows):
        raise AnchoringAuditError("failure inventory does not match supplied candidate banks")

    contexts = {record["paper_key"]: record["context"] for record in records}
    items = [_audit_item(row, contexts[row["paper_key"]], index) for index, row in enumerate(inventory_rows, 1)]
    summary = _build_summary(items)
    manifest = _build_manifest(root, failure_inventory_path, frozen_manifest_path, records, input_paths, out_dir)

    temp_dir = out_dir.parent / f".{out_dir.name}.tmp-{uuid.uuid4().hex}"
    try:
        temp_dir.mkdir(parents=True)
        _write_outputs(temp_dir, summary, items, manifest)
        if out_dir.exists():
            out_dir.rmdir()
        temp_dir.replace(out_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return summary


def _load_and_validate_runs(
    run_dirs: list[Path], root: Path, frozen_path: Path, frozen: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[Path]]:
    papers = {item.get("zotero_key"): item for item in frozen.get("papers", [])}
    if not papers:
        raise AnchoringAuditError("frozen manifest contains no papers")
    records: list[dict[str, Any]] = []
    inputs: list[Path] = [failure_path for failure_path in (frozen_path,)]
    seen: set[str] = set()
    frozen_sha = _sha256_file(frozen_path)
    for supplied_dir in run_dirs:
        run_dir = supplied_dir.resolve()
        run_manifest_path = run_dir / "run_manifest.json"
        run_manifest = _load_json(run_manifest_path)
        plan = run_manifest.get("plan", {})
        selected = run_manifest.get("selected_paper_keys")
        if not isinstance(selected, list) or len(selected) != 1 or selected != plan.get("selected_paper_keys"):
            raise AnchoringAuditError(f"{run_dir}: selected_paper_keys must contain exactly one matching paper")
        paper_key = selected[0]
        if paper_key in seen:
            raise AnchoringAuditError(f"duplicate selected paper key: {paper_key}")
        seen.add(paper_key)
        if paper_key not in papers:
            raise AnchoringAuditError(f"{run_dir}: selected paper is absent from frozen manifest")
        manifest_path = _resolve_from_root(root, plan.get("manifest"), "run frozen manifest")
        if _sha256_file(manifest_path) != frozen_sha:
            raise AnchoringAuditError(f"{run_dir}: frozen manifest SHA-256 mismatch")

        paper = papers[paper_key]
        context_path = _resolve_from_root(root, paper.get("source_clean_context_path"), "clean context")
        pdf_path = Path(paper.get("pdf_path", ""))
        if not pdf_path.is_file():
            raise AnchoringAuditError(f"{run_dir}: frozen PDF is missing")
        if _sha256_file(context_path) != paper.get("clean_context_sha256"):
            raise AnchoringAuditError(f"{run_dir}: clean context SHA-256 mismatch")
        if _sha256_file(pdf_path) != paper.get("pdf_sha256"):
            raise AnchoringAuditError(f"{run_dir}: PDF SHA-256 mismatch")
        verification = _load_json(run_dir / "input_verification.json")
        if verification.get("verified") is not True or verification.get("papers") != [paper_key]:
            raise AnchoringAuditError(f"{run_dir}: input verification mismatch")

        bank_path = run_dir / "papers" / paper_key / "proposed" / "evidence_candidate_bank.json"
        report_path = run_dir / "papers" / paper_key / "proposed" / "candidate_report.json"
        bank = _load_json(bank_path)
        report = _load_json(report_path)
        failures = bank.get("failures")
        if not isinstance(failures, list):
            raise AnchoringAuditError(f"{bank_path}: failures must be a list")
        failure_types = dict(Counter(item.get("error_type", "unknown") for item in failures))
        metadata = bank.get("metadata", {})
        if metadata.get("failed_count") != len(failures) or report.get("failure_types") != failure_types:
            raise AnchoringAuditError(f"{run_dir}: candidate bank/report failure counts disagree")
        source_path = _resolve_from_root(root, metadata.get("source"), "candidate bank source")
        if _sha256_file(source_path) != paper.get("clean_context_sha256"):
            raise AnchoringAuditError(f"{run_dir}: candidate bank source SHA-256 mismatch")
        context = _load_json(context_path)
        if not isinstance(context.get("chunks"), list):
            raise AnchoringAuditError(f"{context_path}: chunks must be a list")
        records.append(
            {
                "paper_key": paper_key,
                "run_name": run_dir.name,
                "bank": bank,
                "context": context,
                "paths": {
                    "run_manifest": run_manifest_path,
                    "input_verification": run_dir / "input_verification.json",
                    "candidate_bank": bank_path,
                    "candidate_report": report_path,
                    "clean_context": context_path,
                    "pdf": pdf_path,
                },
            }
        )
        inputs.extend([run_manifest_path, run_dir / "input_verification.json", bank_path, report_path, context_path, pdf_path])
    return records, list(dict.fromkeys(inputs))


def _failure_rows_from_banks(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for record in records:
        for failure in record["bank"].get("failures", []):
            rows.append(
                {
                    "paper_key": record["paper_key"], "run_name": record["run_name"],
                    "status": str(failure.get("status", "")), "error_type": str(failure.get("error_type", "")),
                    "chunk_id": str(failure.get("chunk_id", "")), "page_start": str(failure.get("page_start", "")),
                    "page_end": str(failure.get("page_end", "")), "evidence_type": str(failure.get("evidence_type", "")),
                    "claim": str(failure.get("claim", "")), "quote_hint": str(failure.get("quote_hint", "")),
                    "message": str(failure.get("message", "")),
                }
            )
    return rows


def _audit_item(row: dict[str, str], context: dict[str, Any], index: int) -> dict[str, Any]:
    chunks = context["chunks"]
    declared = next((chunk for chunk in chunks if chunk.get("chunk_id") == row["chunk_id"]), None)
    if declared is None:
        raise AnchoringAuditError(f"{row['paper_key']}: declared chunk is missing: {row['chunk_id']}")
    hint = row["quote_hint"]
    text = declared.get("text") or ""
    exact_count = text.count(hint) if hint else 0
    current_matches = _normalized_span_matches(hint, text)
    safe_matches, safe_flags = _safe_span_matches(hint, text)
    other_matches = []
    adjacent_matches = []
    other_similarity = 0.0
    declared_index = chunks.index(declared)
    for chunk_index, chunk in enumerate(chunks):
        if chunk is declared:
            continue
        matches, _ = _safe_span_matches(hint, chunk.get("text") or "")
        similarity = _diagnostic_similarity(hint, chunk.get("text") or "")
        if len(matches) == 1:
            other_matches.append(chunk.get("chunk_id", ""))
        if abs(chunk_index - declared_index) == 1 and len(matches) == 1:
            adjacent_matches.append(chunk.get("chunk_id", ""))
        other_similarity = max(other_similarity, similarity)
    non_contiguous = _has_non_contiguous_span(hint, text)
    declared_similarity = _diagnostic_similarity(hint, text)
    mapped = safe_matches[0] if len(safe_matches) == 1 else None
    span_text = text[mapped[0] : mapped[1]] if mapped else ""
    hint_flags = _safe_normalize(hint)[2]
    span_flags = _safe_normalize(span_text)[2] if mapped else set()
    flags = hint_flags | span_flags
    if other_matches:
        flags.add("other_chunk_match")
    if adjacent_matches:
        flags.add("adjacent_chunk_match")
    if non_contiguous:
        flags.add("cross_sentence")

    roundtrip = bool(mapped and text[mapped[0] : mapped[1]] == span_text and _safe_normalize(span_text)[0] == _safe_normalize(hint)[0])
    if exact_count == 1:
        status, eligibility, cause, confidence = "exact_span_available", "eligible_exact", "normalization_gap", "high"
    elif (len(current_matches) == 1 or mapped is not None) and mapped is not None and roundtrip:
        extraction = bool({"nul_character", "soft_hyphen", "zero_width", "linebreak_dehyphenation"} & flags)
        status = "normalized_unique_span_recoverable"
        eligibility = "eligible_after_safe_span_mapping"
        cause = "extraction_noise" if extraction else "normalization_gap"
        confidence = "high"
    elif exact_count > 1 or len(current_matches) > 1 or len(safe_matches) > 1:
        status, eligibility, cause, confidence = "duplicate_span_ambiguous", "not_eligible_ambiguous", "duplicate_text_ambiguity", "high"
    elif other_matches:
        status, eligibility, cause, confidence = "wrong_provenance", "not_eligible_wrong_provenance", "wrong_provenance", "medium"
    elif non_contiguous:
        status, eligibility, cause, confidence = "non_contiguous_span", "not_eligible_non_contiguous", "non_contiguous_span", "medium"
    elif declared_similarity >= 0.65:
        status, eligibility, cause, confidence = "no_verbatim_span", "not_eligible_model_rewrite", "model_rewrite", "medium"
    elif flags & {"nul_character", "soft_hyphen", "zero_width", "linebreak_dehyphenation"}:
        status, eligibility, cause, confidence = "extraction_noise", "needs_review", "extraction_noise", "low"
    else:
        status, eligibility, cause, confidence = "unknown", "needs_review", "unknown", "low"

    return {
        "paper_key": row["paper_key"], "run_name": row["run_name"], "candidate_failure_index": index,
        "chunk_id": row["chunk_id"], "page_start": row["page_start"], "page_end": row["page_end"],
        "evidence_type": row["evidence_type"], "claim": row["claim"], "quote_hint": hint,
        "original_anchoring_error": row["error_type"], "span_traceability_status": status,
        "semantic_support_status": "unreviewed", "verbatim_eligibility": eligibility,
        "suggested_primary_cause": cause, "reviewed_primary_cause": "",
        "secondary_flags": ";".join(sorted(flags)), "suggestion_confidence": confidence,
        "declared_exact_occurrences": exact_count, "current_normalized_occurrences": len(current_matches),
        "safe_normalized_occurrences": len(safe_matches), "other_chunk_matches": ";".join(other_matches),
        "adjacent_chunk_matches": ";".join(adjacent_matches), "mapped_span_start": mapped[0] if mapped else "",
        "mapped_span_end": mapped[1] if mapped else "", "mapped_span_char_count": len(span_text),
        "mapped_span_sha256": _sha256_text(span_text) if span_text else "",
        "mapping_normalization_profile": "safe_nfkc_alnum_v1" if mapped else "",
        "local_mapping_features": ";".join(sorted(flags & {"unicode_nfkc", "unicode_ligature", "nul_character", "soft_hyphen", "zero_width", "linebreak_dehyphenation"})),
        "roundtrip_verified": roundtrip,
        "diagnostic_similarity": round(max(declared_similarity, other_similarity), 6),
    }


def _safe_span_matches(hint: str, text: str) -> tuple[list[tuple[int, int]], set[str]]:
    normalized_hint, _, hint_flags = _safe_normalize(hint)
    normalized_text, mapping, text_flags = _safe_normalize(text)
    if not normalized_hint:
        return [], hint_flags | text_flags
    matches = []
    start = normalized_text.find(normalized_hint)
    while start >= 0:
        end = start + len(normalized_hint)
        matches.append((mapping[start][0], mapping[end - 1][1]))
        start = normalized_text.find(normalized_hint, start + 1)
    return matches, hint_flags | text_flags


def _safe_normalize(value: str) -> tuple[str, list[tuple[int, int]], set[str]]:
    flags: set[str] = set()
    chars: list[str] = []
    mapping: list[tuple[int, int]] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\x00":
            flags.add("nul_character")
            index += 1
            continue
        if char == "\u00ad":
            flags.add("soft_hyphen")
            index += 1
            continue
        if char in {"\u200b", "\u200c", "\u200d", "\ufeff"}:
            flags.add("zero_width")
            index += 1
            continue
        if char == "-" and index > 0 and value[index - 1].isalpha():
            next_index = index + 1
            while next_index < len(value) and value[next_index].isspace():
                next_index += 1
            gap = value[index + 1 : next_index]
            if next_index < len(value) and value[next_index].isalpha() and ("\n" in gap or "\r" in gap):
                flags.add("linebreak_dehyphenation")
                index = next_index
                continue
        normalized = unicodedata.normalize("NFKC", char)
        if normalized != char:
            flags.add("unicode_nfkc")
            if char in {"ﬁ", "ﬂ", "ﬀ", "ﬃ", "ﬄ"}:
                flags.add("unicode_ligature")
        for normalized_char in normalized:
            if normalized_char.isalnum():
                chars.append(normalized_char.casefold())
                mapping.append((index, index + 1))
            else:
                if normalized_char in {"'", '"', "-", "–", "—", "‐", "‑"}:
                    flags.add("punctuation_change")
                if not chars or chars[-1] != " ":
                    chars.append(" ")
                    mapping.append((index, index + 1))
        index += 1
    while chars and chars[0] == " ":
        chars.pop(0)
        mapping.pop(0)
    while chars and chars[-1] == " ":
        chars.pop()
        mapping.pop()
    return "".join(chars), mapping, flags


def _has_non_contiguous_span(hint: str, text: str) -> bool:
    hint_tokens = _safe_normalize(hint)[0].split()
    text_tokens = _safe_normalize(text)[0].split()
    if len(hint_tokens) < 8 or len(text_tokens) < len(hint_tokens):
        return False
    matcher = SequenceMatcher(None, hint_tokens, text_tokens, autojunk=False)
    blocks = [block for block in matcher.get_matching_blocks() if block.size >= 4]
    if len(blocks) < 2 or sum(block.size for block in blocks) < 8:
        return False
    for left, right in zip(blocks, blocks[1:]):
        hint_gap = right.a - (left.a + left.size)
        text_gap = right.b - (left.b + left.size)
        if text_gap >= 2 and hint_gap <= 1:
            return True
    return False


def _diagnostic_similarity(hint: str, text: str) -> float:
    hint_tokens = _safe_normalize(hint)[0].split()
    text_tokens = _safe_normalize(text)[0].split()
    if not hint_tokens or not text_tokens:
        return 0.0
    # Diagnostic-only token LCS coverage; it never changes strict grounding.
    matcher = SequenceMatcher(None, hint_tokens, text_tokens, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()) / len(hint_tokens)


def _build_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "metadata": {
            "audit_rule_version": AUDIT_RULE_VERSION,
            "scope": "verbatim span traceability only",
            "semantic_support_default": "unreviewed",
            "historical_artifacts_modified": False,
            "notes": [
                "This audit does not evaluate claim semantic correctness or paper-summary quality.",
                "Exact-match failure does not establish a semantic error or hallucination.",
                "Exact-span availability does not establish semantic correctness.",
            ],
        },
        "total_failures": len(items),
        "span_traceability_statuses": dict(Counter(item["span_traceability_status"] for item in items)),
        "suggested_primary_causes": dict(Counter(item["suggested_primary_cause"] for item in items)),
        "by_paper": _nested_counts(items, "paper_key"),
        "by_evidence_type": _nested_counts(items, "evidence_type"),
        "verbatim_eligibility": dict(Counter(item["verbatim_eligibility"] for item in items)),
    }


def _nested_counts(items: list[dict[str, Any]], field: str) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for value in sorted({str(item[field]) for item in items}):
        subset = [item for item in items if str(item[field]) == value]
        result[value] = dict(Counter(item["suggested_primary_cause"] for item in subset))
    return result


def _build_manifest(
    root: Path,
    inventory_path: Path,
    frozen_path: Path,
    records: list[dict[str, Any]],
    input_paths: list[Path],
    out_dir: Path,
) -> dict[str, Any]:
    return {
        "audit_rule_version": AUDIT_RULE_VERSION,
        "git": _git_state(root),
        "inputs": [_path_record(path, root, redact=path.suffix.lower() == ".pdf") for path in input_paths],
        "runs": [
            {"paper_key": record["paper_key"], "run_name": record["run_name"], "candidate_bank_sha256": _sha256_file(record["paths"]["candidate_bank"])}
            for record in records
        ],
        "failure_inventory_sha256": _sha256_file(inventory_path),
        "frozen_manifest_sha256": _sha256_file(frozen_path),
        "output_directory": _path_record(out_dir, root, redact=False, allow_missing=True),
        "output_policy": "temporary directory followed by atomic rename; output must be absent or empty",
    }


def _write_outputs(out_dir: Path, summary: dict[str, Any], items: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    _atomic_write(out_dir / "audit_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(out_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    _write_csv(out_dir / "items.csv", items, ITEM_FIELDS)
    lines = [
        "# Anchoring Failure Span-Traceability Audit", "",
        f"- Failures audited: {summary['total_failures']}",
        "- Scope: verbatim span traceability only; semantic support is unreviewed.",
        "- Exact-match failure is not a semantic-error or hallucination finding.",
        "- Exact-span availability is not semantic-correctness proof.",
        "- Historical Run 002 artifacts and metrics were not modified.",
        "", "## Span Traceability", "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in sorted(summary["span_traceability_statuses"].items()))
    lines.extend(["", "## Suggested Primary Cause", ""])
    lines.extend(f"- {name}: {count}" for name, count in sorted(summary["suggested_primary_causes"].items()))
    _atomic_write(out_dir / "summary.md", "\n".join(lines) + "\n")


def _read_inventory(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise AnchoringAuditError(f"failure inventory is missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != INVENTORY_FIELDS:
            raise AnchoringAuditError("failure inventory has unexpected or duplicate headers")
        rows = list(reader)
    if not rows:
        raise AnchoringAuditError("failure inventory has no rows")
    return rows


def _row_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(str(row.get(field, "")) for field in INVENTORY_FIELDS)


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise AnchoringAuditError(f"required file is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _resolve_from_root(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AnchoringAuditError(f"{label} path is missing")
    path = Path(value)
    resolved = path if path.is_absolute() else root / path
    if not resolved.is_file():
        raise AnchoringAuditError(f"{label} is missing: {resolved}")
    return resolved


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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _path_record(path: Path, root: Path, *, redact: bool, allow_missing: bool = False) -> dict[str, str]:
    if redact:
        return {"path_type": "private_local_path_redacted", "sha256": _sha256_file(path)}
    resolved = path.resolve()
    try:
        relative = os.path.relpath(resolved, root.resolve()).replace("\\", "/")
        record = {"path": relative, "path_type": "relative_to_repo"}
    except ValueError:
        record = {"path_type": "private_local_path_redacted"}
    if path.is_file():
        record["sha256"] = _sha256_file(path)
    elif not allow_missing:
        raise AnchoringAuditError(f"path is missing: {path}")
    return record


def _git_state(root: Path) -> dict[str, Any]:
    sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=False)
    return {"commit_sha": sha.stdout.strip() if sha.returncode == 0 else "unknown", "worktree": "clean" if status.returncode == 0 and not status.stdout.strip() else "dirty"}
