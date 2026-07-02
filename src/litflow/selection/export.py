from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def load_selected_papers(selected_path: Path) -> list[dict[str, Any]]:
    data = json.loads(selected_path.read_text(encoding="utf-8-sig"))
    rows = data.get("papers")
    if not isinstance(rows, list):
        raise ValueError("selected_candidates.json must contain a papers list")

    selected: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or "selected" not in row or "paper" not in row:
            raise ValueError(f"invalid selected_candidates.json row {index}")
        if row["selected"] is True:
            paper = row["paper"]
            if not isinstance(paper, dict):
                raise ValueError(f"invalid selected_candidates.json row {index}: paper must be an object")
            selected.append(paper)
    return selected


def export_zotero_import(selected_path: Path, output_path: Path, output_format: str) -> int:
    papers = load_selected_papers(selected_path)
    if not papers:
        raise ValueError("No papers with selected=true; nothing to export")

    if output_format == "bib":
        text = "\n\n".join(_to_bibtex(paper) for paper in papers) + "\n"
    elif output_format == "ris":
        text = "\n".join(_to_ris(paper) for paper in papers) + "\n"
    else:
        raise ValueError(f"Unsupported export format: {output_format}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return len(papers)


def make_citation_key(paper: dict[str, Any]) -> str:
    authors = paper.get("authors") or []
    first_author = str(authors[0]) if authors else "anon"
    surname = _author_surname(first_author)
    year = str(paper.get("year") or "n.d")
    title_words = re.findall(r"[A-Za-z0-9]+", str(paper.get("title") or "").lower())
    title_slug = "".join(_slug(word) for word in title_words[:3]) or "untitled"
    return f"{surname}{year}{title_slug}"


def _to_bibtex(paper: dict[str, Any]) -> str:
    entry_type = _bibtex_entry_type(paper)
    fields = [
        ("title", paper.get("title")),
        ("author", " and ".join(str(author) for author in paper.get("authors") or [])),
        ("year", paper.get("year")),
        ("journal", paper.get("venue") if entry_type == "article" else None),
        ("howpublished", paper.get("venue") if entry_type == "misc" else None),
        ("doi", paper.get("doi")),
        ("url", paper.get("url")),
        ("abstract", paper.get("abstract")),
    ]
    lines = [f"@{entry_type}{{{make_citation_key(paper)},"]
    for key, value in fields:
        if value not in (None, "", []):
            lines.append(f"  {key} = {{{_escape_bibtex(str(value))}}},")
    lines.append("}")
    return "\n".join(lines)


def _to_ris(paper: dict[str, Any]) -> str:
    ty = "JOUR" if _bibtex_entry_type(paper) == "article" else "GEN"
    lines = [f"TY  - {ty}"]
    _add_ris(lines, "TI", paper.get("title"))
    for author in paper.get("authors") or []:
        _add_ris(lines, "AU", author)
    _add_ris(lines, "PY", paper.get("year"))
    _add_ris(lines, "JO", paper.get("venue"))
    _add_ris(lines, "DO", paper.get("doi"))
    _add_ris(lines, "UR", paper.get("url"))
    _add_ris(lines, "AB", paper.get("abstract"))
    lines.append("ER  -")
    return "\n".join(lines)


def _bibtex_entry_type(paper: dict[str, Any]) -> str:
    venue = str(paper.get("venue") or "").casefold()
    if "journal" in venue or "transactions" in venue:
        return "article"
    return "misc"


def _add_ris(lines: list[str], tag: str, value: Any) -> None:
    if value not in (None, "", []):
        lines.append(f"{tag}  - {value}")


def _escape_bibtex(value: str) -> str:
    return value.replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def _author_surname(author: str) -> str:
    parts = [part for part in author.split() if part]
    if not parts:
        return "anon"
    # ponytail: small Chinese surname heuristic; add a real name parser only if keys become a problem.
    chinese_surnames = {"chen", "li", "liu", "wang", "wu", "xu", "yang", "zhang", "zhao", "zhou"}
    first = _slug(parts[0])
    if first in chinese_surnames:
        return first
    return _slug(parts[-1]) or "anon"
