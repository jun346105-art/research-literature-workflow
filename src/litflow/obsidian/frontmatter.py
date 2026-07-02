from __future__ import annotations

import json
from typing import Any

FRONTMATTER_FIELDS = (
    "citekey",
    "zotero_key",
    "doi",
    "title",
    "authors",
    "year",
    "venue",
    "paper_type",
    "reading_status",
    "source",
    "pdf_attachment_path",
    "pdf_exists",
    "attachment_count",
    "research_domain",
    "research_problem",
    "application_scenario",
    "method_family",
    "model_type",
    "solution_type",
    "objective_type",
    "static_or_dynamic",
    "data_source",
    "dataset_size",
    "code_available",
    "evidence_level",
    "relevance_to_my_research",
    "tags",
    "created",
    "updated",
)


def build_frontmatter(paper: dict[str, Any], today: str) -> str:
    data = {
        "citekey": paper.get("citation_key") or "",
        "zotero_key": paper.get("zotero_key") or "",
        "doi": paper.get("doi") or "",
        "title": paper.get("title") or "",
        "authors": paper.get("authors") or [],
        "year": paper.get("year"),
        "venue": paper.get("venue") or "",
        "paper_type": paper.get("item_type") or "",
        "reading_status": "inbox",
        "source": "zotero",
        "pdf_attachment_path": paper.get("pdf_attachment_path") or "",
        "pdf_exists": bool(paper.get("pdf_exists")),
        "attachment_count": int(paper.get("attachment_count") or 0),
        "research_domain": "",
        "research_problem": "",
        "application_scenario": "",
        "method_family": "",
        "model_type": "",
        "solution_type": "",
        "objective_type": "",
        "static_or_dynamic": "",
        "data_source": "",
        "dataset_size": "",
        "code_available": "",
        "evidence_level": "",
        "relevance_to_my_research": "",
        "tags": paper.get("tags") or [],
        "created": today,
        "updated": today,
    }
    lines = ["---"]
    for key in FRONTMATTER_FIELDS:
        lines.append(f"{key}: {_yaml_value(data[key])}")
    lines.append("---")
    return "\n".join(lines)


def _yaml_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)

