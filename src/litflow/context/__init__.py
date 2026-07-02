from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from litflow.context.annotation_aligner import align_annotations
from litflow.context.chunker import chunk_pages
from litflow.context.cleaner import clean_pages
from litflow.context.section_detector import detect_sections


def clean_reading_contexts(
    context_dir: Path,
    manifest_path: Path,
    out_dir: Path,
    out_manifest: Path,
    *,
    chunk_size: int = 3500,
    overlap: int = 400,
) -> dict[str, Any]:
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_manifest.parent.mkdir(parents=True, exist_ok=True)
    items = []
    warnings: list[str] = []
    for row in source_manifest.get("items", []):
        source_path = Path(row.get("context_path") or context_dir / f"{row.get('zotero_key')}.json")
        if not source_path.is_absolute():
            source_path = Path(source_path)
        try:
            context = json.loads(source_path.read_text(encoding="utf-8-sig"))
            clean = clean_one_context(context, chunk_size=chunk_size, overlap=overlap)
            clean_path = out_dir / f"{context['metadata']['zotero_key']}.json"
            clean_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            status = clean["quality"]["status"]
        except Exception as exc:
            clean_path = out_dir / f"{row.get('zotero_key', 'unknown')}.json"
            clean = None
            status = "failed"
            warnings.append(f"{row.get('zotero_key')}: {exc}")
        items.append(_manifest_row(row, clean, clean_path, status))

    manifest = {
        "metadata": {
            "source_manifest": str(manifest_path),
            "output_dir": str(out_dir),
            "total_items": len(items),
            "success_count": sum(1 for item in items if item["status"] == "ok"),
            "failed_count": sum(1 for item in items if item["status"] == "failed"),
            "total_chunks": sum(item["chunk_count"] for item in items),
            "total_annotations": sum(item["annotation_count"] for item in items),
            "total_aligned_annotations": sum(item["aligned_annotation_count"] for item in items),
        },
        "items": items,
        "warnings": warnings,
    }
    out_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def clean_one_context(context: dict[str, Any], *, chunk_size: int = 3500, overlap: int = 400) -> dict[str, Any]:
    metadata = context["metadata"]
    pages, cleaning = clean_pages(context.get("pdf_text", {}).get("pages", []))
    pages, sections = detect_sections(pages)
    chunks = chunk_pages(
        pages,
        zotero_key=metadata.get("zotero_key") or "",
        citation_key=metadata.get("citation_key"),
        title=metadata.get("title") or "",
        chunk_size_chars=chunk_size,
        chunk_overlap_chars=overlap,
    )
    annotations, chunks = align_annotations(context.get("zotero_notes", {}), pages, chunks)
    quality = _quality(context, cleaning, chunks, annotations, sections)
    return {
        "metadata": {
            "zotero_key": metadata.get("zotero_key") or "",
            "citation_key": metadata.get("citation_key"),
            "title": metadata.get("title") or "",
            "authors": metadata.get("authors") or [],
            "year": metadata.get("year"),
            "doi": metadata.get("doi") or "",
            "pdf_attachment_path": metadata.get("pdf_attachment_path") or "",
        },
        "cleaning": cleaning,
        "sections": sections,
        "chunks": [chunk.model_dump() for chunk in chunks],
        "annotations": annotations,
        "quality": quality,
    }


def _quality(context: dict[str, Any], cleaning: dict, chunks: list, annotations: dict, sections: list[dict]) -> dict[str, Any]:
    warnings = list(context.get("processing", {}).get("warnings", []))
    errors = list(context.get("processing", {}).get("errors", []))
    if cleaning["cleaned_char_count"] == 0:
        warnings.append("PDF text is empty")
    if cleaning["cleaned_char_count"] < 1000:
        warnings.append("cleaned_char_count is below 1000")
    if len(chunks) == 0:
        warnings.append("chunk_count is 0")
    if cleaning["page_count"] == 0:
        warnings.append("page_count is 0")
    if annotations["items"] and annotations["aligned_count"] == 0:
        warnings.append("annotations exist but none aligned")
    if any(section["section_guess"] == "references" for section in sections):
        warnings.append("references section detected")
    if any("limited to first" in warning for warning in warnings):
        warnings.append("Phase 3A may have used max_pages; context may be incomplete")
    return {"status": "ok" if not errors else "error", "warnings": warnings, "errors": errors}


def _manifest_row(source_row: dict, clean: dict | None, clean_path: Path, status: str) -> dict[str, Any]:
    if not clean:
        return {
            "zotero_key": source_row.get("zotero_key") or "",
            "citation_key": source_row.get("citation_key"),
            "title": source_row.get("title") or "",
            "clean_context_path": str(clean_path),
            "page_count": 0,
            "cleaned_char_count": 0,
            "chunk_count": 0,
            "annotation_count": 0,
            "aligned_annotation_count": 0,
            "status": "failed",
        }
    return {
        "zotero_key": clean["metadata"]["zotero_key"],
        "citation_key": clean["metadata"]["citation_key"],
        "title": clean["metadata"]["title"],
        "clean_context_path": str(clean_path),
        "page_count": clean["cleaning"]["page_count"],
        "cleaned_char_count": clean["cleaning"]["cleaned_char_count"],
        "chunk_count": len(clean["chunks"]),
        "annotation_count": len(clean["annotations"]["items"]),
        "aligned_annotation_count": clean["annotations"]["aligned_count"],
        "status": status,
    }


def section_distribution(clean: dict[str, Any]) -> dict[str, int]:
    return dict(Counter(chunk["section_guess"] for chunk in clean.get("chunks", [])))
