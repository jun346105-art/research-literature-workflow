from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PaperMetadata:
    zotero_key: str
    citation_key: str | None
    citation_key_source: str | None
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    item_type: str | None = None
    collection: str | None = None
    tags: list[str] = field(default_factory=list)
    pdf_attachment_path: str | None = None
    pdf_exists: bool = False
    attachment_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "zotero_key": self.zotero_key,
            "citation_key": self.citation_key,
            "citation_key_source": self.citation_key_source,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "doi": self.doi,
            "url": self.url,
            "abstract": self.abstract,
            "item_type": self.item_type,
            "collection": self.collection,
            "tags": self.tags,
            "pdf_attachment_path": self.pdf_attachment_path,
            "pdf_exists": self.pdf_exists,
            "attachment_count": self.attachment_count,
        }
