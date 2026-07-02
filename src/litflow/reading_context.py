from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from litflow.pdf.extractor import extract_pdf_text
from litflow.zotero.annotations import ZoteroChildrenReadable, read_zotero_notes


def build_reading_contexts(
    items_path: Path,
    out_dir: Path,
    manifest_path: Path,
    *,
    max_pages: int | None = None,
    zotero_client: ZoteroChildrenReadable | None = None,
) -> dict[str, Any]:
    data = json.loads(items_path.read_text(encoding="utf-8-sig"))
    papers = data.get("papers")
    if not isinstance(papers, list):
        raise ValueError("zotero_collection.json must contain a papers list")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "metadata": {
            "source": str(items_path),
            "output_dir": str(out_dir),
            "total_items": len(papers),
            "success_count": 0,
            "missing_pdf_count": 0,
            "pdf_extract_failed_count": 0,
            "annotation_read_failed_count": 0,
        },
        "items": [],
        "warnings": [],
    }

    for paper in papers:
        context = _build_one_context(paper, max_pages=max_pages, zotero_client=zotero_client)
        context_path = out_dir / f"{paper.get('zotero_key')}.json"
        context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pdf_text = context["pdf_text"]
        notes = context["zotero_notes"]
        status = context["processing"]["status"]

        if not context["metadata"]["pdf_exists"]:
            manifest["metadata"]["missing_pdf_count"] += 1
        if pdf_text["errors"]:
            manifest["metadata"]["pdf_extract_failed_count"] += 1
        if notes["warnings"]:
            manifest["metadata"]["annotation_read_failed_count"] += 1
        if status == "success":
            manifest["metadata"]["success_count"] += 1
        manifest["warnings"].extend(f"{paper.get('zotero_key')}: {warning}" for warning in context["processing"]["warnings"])
        manifest["items"].append(
            {
                "zotero_key": paper.get("zotero_key") or "",
                "citation_key": paper.get("citation_key"),
                "title": paper.get("title") or "",
                "context_path": str(context_path),
                "pdf_exists": bool(context["metadata"]["pdf_exists"]),
                "page_count": pdf_text["page_count"],
                "char_count": pdf_text["char_count"],
                "annotation_count": notes["annotation_count"],
                "note_count": notes["note_count"],
                "status": status,
            }
        )

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _build_one_context(
    paper: dict[str, Any],
    *,
    max_pages: int | None,
    zotero_client: ZoteroChildrenReadable | None,
) -> dict[str, Any]:
    pdf = extract_pdf_text(paper.get("pdf_attachment_path"), max_pages=max_pages)
    notes = read_zotero_notes(paper.get("zotero_key") or "", zotero_client)
    warnings = [*pdf.warnings, *notes["warnings"]]
    errors = [*pdf.errors]
    if not paper.get("pdf_exists"):
        warnings.append("PDF marked missing in Zotero snapshot")
    status = "success" if not errors else "pdf_extract_failed"
    return {
        "metadata": {
            "zotero_key": paper.get("zotero_key") or "",
            "citation_key": paper.get("citation_key"),
            "title": paper.get("title") or "",
            "authors": paper.get("authors") or [],
            "year": paper.get("year"),
            "venue": paper.get("venue") or "",
            "doi": paper.get("doi") or "",
            "abstract": paper.get("abstract") or "",
            "pdf_attachment_path": paper.get("pdf_attachment_path") or "",
            "pdf_exists": bool(paper.get("pdf_exists")),
        },
        "pdf_text": pdf.to_dict(),
        "zotero_notes": notes,
        "processing": {
            "status": status,
            "warnings": warnings,
            "errors": errors,
        },
    }

