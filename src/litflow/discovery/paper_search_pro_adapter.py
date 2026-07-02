from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from litflow.models import ALLOWED_BUCKETS, CandidatePaper, CandidatePool


def build_candidate_pool(input_path: Path) -> CandidatePool:
    papers_path = _resolve_input(input_path)
    rows = _read_rows(papers_path)
    warnings: list[str] = []
    papers: list[CandidatePaper] = []
    for index, row in enumerate(rows, start=1):
        try:
            if not isinstance(row, dict):
                warnings.append(f"row {index}: malformed record skipped")
                continue
            title = _get_text(row, "title", "Title", "paper_title")
            if not title:
                warnings.append(f"row {index}: missing title, skipped")
                continue
            paper = _normalize_row(row, title)
            _add_missing_warnings(warnings, index, paper)
            papers.append(paper)
        except Exception as exc:
            warnings.append(f"row {index}: malformed record skipped: {exc}")
    return CandidatePool.deduped(papers, warnings)


def write_candidate_pool(pool: CandidatePool, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(pool.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _resolve_input(input_path: Path) -> Path:
    if input_path.is_dir():
        json_path = input_path / "papers.json"
        if json_path.exists():
            return json_path
        csv_path = input_path / "papers.csv"
        if csv_path.exists():
            return csv_path
    if not input_path.exists():
        raise FileNotFoundError(f"paper-search-pro output not found: {input_path}")
    if input_path.suffix.casefold() not in {".json", ".csv"}:
        raise ValueError(f"Unsupported input file type: {input_path.suffix}")
    return input_path


def _read_rows(input_path: Path) -> list[Any]:
    if input_path.suffix.casefold() == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]
    data = json.loads(input_path.read_text(encoding="utf-8-sig"))
    return _extract_rows(data)


def _extract_rows(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("papers", "results", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("Unsupported papers.json shape: expected a list or a dict with papers/results/items")


def _normalize_row(row: dict[str, Any], title: str) -> CandidatePaper:
    return CandidatePaper(
        title=title,
        authors=_get_authors(row),
        year=_get_year(row),
        doi=_get_text(row, "doi", "DOI"),
        url=_get_text(row, "url", "URL", "link", "paper_url"),
        abstract=_get_text(row, "abstract", "Abstract", "summary"),
        venue=_get_text(row, "venue", "Venue", "journal", "conference"),
        source=_get_text(row, "source", "database"),
        citation_count=_get_int(row, "citation_count", "citations", "citationCount"),
        relevance_score=_get_float(row, "relevance_score", "score"),
        tier=_get_text(row, "tier"),
        search_query=_get_text(row, "search_query", "query"),
        recommended_bucket=_get_bucket(row),
        source_id=_get_text(row, "id", "paper_id", "source_id"),
        keywords=_get_list(row, "keywords", "tags"),
        raw=row,
    )


def _get_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return str(value)
    return None


def _get_list(row: dict[str, Any], *keys: str) -> list[str]:
    for key in keys:
        value = row.get(key)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
    return []


def _get_authors(row: dict[str, Any]) -> list[str]:
    value = _get_value(row, "authors", "Authors", "author")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    text = value.strip()
    if not text:
        return []
    for delimiter in (";", ",", " and "):
        if delimiter in text:
            return [part.strip() for part in text.split(delimiter) if part.strip()]
    return [text]


def _get_year(row: dict[str, Any]) -> int | None:
    value = _get_value(row, "year", "Year", "publication_year", "published")
    if value is None:
        return None
    text = str(value)
    for part in text.replace("-", " ").split():
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def _get_int(row: dict[str, Any], *keys: str) -> int | None:
    value = _get_value(row, *keys)
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except ValueError:
        return None


def _get_float(row: dict[str, Any], *keys: str) -> float | None:
    value = _get_value(row, *keys)
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _get_bucket(row: dict[str, Any]) -> str:
    bucket = _get_text(row, "recommended_bucket", "bucket")
    if bucket in ALLOWED_BUCKETS:
        return bucket
    return "uncertain"


def _get_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _add_missing_warnings(warnings: list[str], index: int, paper: CandidatePaper) -> None:
    if not paper.doi:
        warnings.append(f"row {index}: missing DOI")
    if not paper.abstract:
        warnings.append(f"row {index}: missing abstract")
    if paper.citation_count is None:
        warnings.append(f"row {index}: missing citation_count")
