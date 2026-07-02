from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

KEY_SECTIONS = {"abstract", "introduction", "method", "experiment", "results", "discussion", "conclusion"}


def audit_clean_contexts(clean_dir: Path, manifest_path: Path, output_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    items = []
    warnings: list[str] = []
    for row in manifest.get("items", []):
        path = Path(row.get("clean_context_path") or clean_dir / f"{row.get('zotero_key')}.json")
        if not path.is_absolute():
            path = Path(path)
        try:
            clean = json.loads(path.read_text(encoding="utf-8-sig"))
            item = audit_one_clean_context(clean, str(path))
        except Exception as exc:
            item = {
                "zotero_key": row.get("zotero_key") or "",
                "citation_key": row.get("citation_key"),
                "title": row.get("title") or "",
                "clean_context_path": str(path),
                "quality_status": "failed",
                "page_count": 0,
                "cleaned_char_count": 0,
                "chunk_count": 0,
                "section_distribution": {},
                "annotation_count": 0,
                "aligned_annotation_count": 0,
                "warnings": [],
                "errors": [str(exc)],
                "recommendation": "Fix clean context generation before LLM reading.",
            }
        items.append(item)
        warnings.extend(f"{item['zotero_key']}: {warning}" for warning in item["warnings"])

    report = {
        "metadata": {
            "source_manifest": str(manifest_path),
            "total_items": len(items),
            "ready_for_llm_count": sum(1 for item in items if item["quality_status"] == "ready_for_llm"),
            "needs_manual_check_count": sum(1 for item in items if item["quality_status"] == "needs_manual_check"),
            "failed_count": sum(1 for item in items if item["quality_status"] == "failed"),
        },
        "items": items,
        "warnings": warnings,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def audit_one_clean_context(clean: dict[str, Any], clean_context_path: str = "") -> dict[str, Any]:
    metadata = clean.get("metadata", {})
    cleaning = clean.get("cleaning", {})
    chunks = clean.get("chunks", [])
    annotations = clean.get("annotations", {})
    quality = clean.get("quality", {})
    page_count = int(cleaning.get("page_count") or 0)
    cleaned_char_count = int(cleaning.get("cleaned_char_count") or 0)
    chunk_count = len(chunks)
    section_distribution = dict(Counter(chunk.get("section_guess", "unknown") for chunk in chunks))
    annotation_count = len(annotations.get("items", []))
    aligned_annotation_count = int(annotations.get("aligned_count") or 0)
    warnings = list(quality.get("warnings", []))
    errors = list(quality.get("errors", []))

    _add_quality_warnings(
        warnings,
        page_count=page_count,
        cleaned_char_count=cleaned_char_count,
        chunk_count=chunk_count,
        section_distribution=section_distribution,
        annotation_count=annotation_count,
        aligned_annotation_count=aligned_annotation_count,
        chunks=chunks,
    )

    status = _status(page_count, cleaned_char_count, chunk_count, warnings, errors)
    return {
        "zotero_key": metadata.get("zotero_key") or "",
        "citation_key": metadata.get("citation_key"),
        "title": metadata.get("title") or "",
        "clean_context_path": clean_context_path,
        "quality_status": status,
        "page_count": page_count,
        "cleaned_char_count": cleaned_char_count,
        "chunk_count": chunk_count,
        "section_distribution": section_distribution,
        "annotation_count": annotation_count,
        "aligned_annotation_count": aligned_annotation_count,
        "warnings": warnings,
        "errors": errors,
        "recommendation": _recommendation(status),
    }


def _add_quality_warnings(
    warnings: list[str],
    *,
    page_count: int,
    cleaned_char_count: int,
    chunk_count: int,
    section_distribution: dict[str, int],
    annotation_count: int,
    aligned_annotation_count: int,
    chunks: list[dict[str, Any]],
) -> None:
    if cleaned_char_count == 0:
        warnings.append("cleaned_char_count is 0; possible empty or scanned PDF")
    elif cleaned_char_count < 3000:
        warnings.append("cleaned_char_count is below 3000")
    if chunk_count == 0:
        warnings.append("chunk_count is 0")
    if page_count == 0:
        warnings.append("page_count is 0")
    if _has_incomplete_warning(warnings):
        warnings.append("max_pages/context incomplete warning detected")
    if chunk_count and section_distribution.get("unknown", 0) == chunk_count:
        warnings.append("all chunks have unknown section")
    if chunk_count and not (set(section_distribution) & KEY_SECTIONS):
        warnings.append("no key academic sections detected")
    if _reference_ratio(section_distribution) > 0.5:
        warnings.append("references chunk ratio is above 50%")
    if annotation_count and aligned_annotation_count == 0:
        warnings.append("annotations exist but none aligned")
    for chunk in chunks:
        char_count = int(chunk.get("char_count") or 0)
        if char_count > 4500:
            warnings.append(f"chunk {chunk.get('chunk_id')} is unusually long")
        if char_count and char_count < 200:
            warnings.append(f"chunk {chunk.get('chunk_id')} is unusually short")


def _status(page_count: int, cleaned_char_count: int, chunk_count: int, warnings: list[str], errors: list[str]) -> str:
    if errors or page_count == 0 or cleaned_char_count == 0 or chunk_count == 0:
        return "failed"
    if cleaned_char_count < 3000 or _has_incomplete_warning(warnings):
        return "needs_manual_check"
    manual_signals = (
        "all chunks have unknown section",
        "no key academic sections detected",
        "references chunk ratio is above 50%",
        "annotations exist but none aligned",
    )
    if any(signal in warnings for signal in manual_signals):
        return "needs_manual_check"
    return "ready_for_llm"


def _reference_ratio(section_distribution: dict[str, int]) -> float:
    total = sum(section_distribution.values())
    return (section_distribution.get("references", 0) / total) if total else 0.0


def _has_incomplete_warning(warnings: list[str]) -> bool:
    return any("max_pages" in warning or "incomplete" in warning or "limited to first" in warning for warning in warnings)


def _recommendation(status: str) -> str:
    if status == "ready_for_llm":
        return "Ready for Phase 4A LLM reading."
    if status == "needs_manual_check":
        return "Review PDF extraction quality or Zotero notes before LLM reading."
    return "Do not send to LLM reading until extraction errors are fixed."

