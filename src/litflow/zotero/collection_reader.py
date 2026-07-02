from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from litflow.zotero.client import ZoteroReadClient
from litflow.zotero.models import PaperMetadata


class ZoteroReadable(Protocol):
    def get_collections(self) -> list[dict[str, Any]]: ...
    def get_collection_items(self, collection_key: str) -> list[dict[str, Any]]: ...
    def get_items(self) -> list[dict[str, Any]]: ...
    def get_item_children(self, item_key: str) -> list[dict[str, Any]]: ...
    def get_attachment_file_path(self, attachment_key: str) -> str | None: ...


def read_collection(collection_name: str, client: ZoteroReadable | None = None) -> list[PaperMetadata]:
    client = client or ZoteroReadClient()
    collection = _find_collection(client.get_collections(), collection_name)
    if collection is None:
        raise ValueError(f"Zotero collection not found: {collection_name}")

    collection_key = collection["key"]
    papers: list[PaperMetadata] = []
    items = client.get_collection_items(collection_key)
    if not items:
        items = [item for item in client.get_items() if collection_key in item.get("data", {}).get("collections", [])]
    for item in items:
        data = item.get("data", {})
        if data.get("itemType") in {"attachment", "note"}:
            continue
        papers.append(_item_to_metadata(item, collection_name, client))
    return papers


def write_collection_snapshot(collection_name: str, output_path: Path, client: ZoteroReadable | None = None) -> list[PaperMetadata]:
    papers = read_collection(collection_name, client)
    source_counts = Counter(paper.citation_key_source or "missing" for paper in papers)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "source": "zotero",
                    "collection": collection_name,
                    "item_count": len(papers),
                    "total_items": len(papers),
                    "citation_key_count": sum(1 for paper in papers if paper.citation_key),
                    "citation_key_missing_count": sum(1 for paper in papers if not paper.citation_key),
                    "citation_key_sources": dict(source_counts),
                    "read_only": True,
                },
                "papers": [paper.to_dict() for paper in papers],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return papers


def _find_collection(collections: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for collection in collections:
        data = collection.get("data", {})
        if data.get("name") == name:
            return collection
    return None


def _item_to_metadata(item: dict[str, Any], collection_name: str, client: ZoteroReadable) -> PaperMetadata:
    data = item.get("data", {})
    key = item.get("key") or data.get("key") or ""
    attachments = client.get_item_children(key)
    pdf_attachments = [_attachment for _attachment in attachments if _is_pdf_attachment(_attachment)]
    pdf_path = _first_pdf_path(pdf_attachments, client)
    citation_key, citation_key_source = _citation_key(data)
    return PaperMetadata(
        zotero_key=key,
        citation_key=citation_key,
        citation_key_source=citation_key_source,
        title=data.get("title") or "",
        authors=_authors(data),
        year=_year(data.get("date")),
        venue=_venue(data),
        doi=data.get("DOI") or data.get("doi"),
        url=data.get("url"),
        abstract=data.get("abstractNote"),
        item_type=data.get("itemType"),
        collection=collection_name,
        tags=[tag.get("tag") for tag in data.get("tags", []) if tag.get("tag")],
        pdf_attachment_path=pdf_path,
        pdf_exists=Path(pdf_path).exists() if pdf_path else False,
        attachment_count=len(attachments),
    )


def _authors(data: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    for creator in data.get("creators", []):
        name = creator.get("name")
        if name:
            authors.append(name)
            continue
        full_name = " ".join(part for part in [creator.get("firstName"), creator.get("lastName")] if part)
        if full_name:
            authors.append(full_name)
    return authors


def _year(value: Any) -> int | None:
    if not value:
        return None
    match = re.search(r"\b(\d{4})\b", str(value))
    return int(match.group(1)) if match else None


def _venue(data: dict[str, Any]) -> str | None:
    for key in ("publicationTitle", "conferenceName", "proceedingsTitle", "bookTitle", "publisher"):
        if data.get(key):
            return data[key]
    return None


def _citation_key(data: dict[str, Any]) -> tuple[str | None, str]:
    if data.get("citationKey"):
        return data["citationKey"], "better_bibtex"
    if data.get("citekey"):
        return data["citekey"], "zotero_field"
    extra = data.get("extra") or ""
    match = re.search(
        r"^(?:Citation Key|Better BibTeX citation key|BibTeX key|citekey):\s*(\S+)",
        extra,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if match:
        return match.group(1), "extra_field"
    return None, "missing"


def citation_key_candidate_fields(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data", {})
    candidates = {
        "data.citationKey": data.get("citationKey"),
        "data.citekey": data.get("citekey"),
        "data.extra": data.get("extra"),
        "data.key": data.get("key"),
    }
    for key, value in data.items():
        if "cit" in key.casefold() or "bib" in key.casefold():
            candidates[f"data.{key}"] = value
    return candidates


def _is_pdf_attachment(item: dict[str, Any]) -> bool:
    data = item.get("data", {})
    title = str(data.get("title") or "")
    path = str(data.get("path") or "")
    content_type = str(data.get("contentType") or "")
    return content_type == "application/pdf" or title.lower().endswith(".pdf") or path.lower().endswith(".pdf")


def _first_pdf_path(pdf_attachments: list[dict[str, Any]], client: ZoteroReadable) -> str | None:
    for attachment in pdf_attachments:
        data = attachment.get("data", {})
        key = attachment.get("key") or data.get("key")
        if key:
            path = client.get_attachment_file_path(key)
            if path:
                return path
        raw_path = data.get("path")
        if raw_path and not str(raw_path).startswith("storage:"):
            return str(raw_path)
    return None
