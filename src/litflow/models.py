from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ALLOWED_BUCKETS = {
    "classic_highly_cited",
    "frontier_recent",
    "practical_reliable",
    "review_or_survey",
    "uncertain",
}


def normalize_title(value: str) -> str:
    return " ".join(value.casefold().split())


@dataclass(frozen=True)
class CandidatePaper:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    venue: str | None = None
    source: str | None = None
    citation_count: int | None = None
    relevance_score: float | None = None
    tier: str | None = None
    search_query: str | None = None
    recommended_bucket: str = "uncertain"
    source_id: str | None = None
    keywords: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.recommended_bucket not in ALLOWED_BUCKETS:
            raise ValueError(f"Invalid recommended_bucket: {self.recommended_bucket}")

    @property
    def dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.casefold().strip()}"
        return f"title:{normalize_title(self.title)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "doi": self.doi,
            "url": self.url,
            "abstract": self.abstract,
            "venue": self.venue,
            "source": self.source,
            "citation_count": self.citation_count,
            "relevance_score": self.relevance_score,
            "tier": self.tier,
            "search_query": self.search_query,
            "recommended_bucket": self.recommended_bucket,
            "source_id": self.source_id,
            "keywords": self.keywords,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class CandidatePool:
    papers: list[CandidatePaper]
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def deduped(cls, papers: list[CandidatePaper], warnings: list[str] | None = None) -> CandidatePool:
        warnings = list(warnings or [])
        seen: set[str] = set()
        result: list[CandidatePaper] = []
        for paper in papers:
            key = paper.dedupe_key
            if key in seen:
                warnings.append(f"duplicate paper removed: {paper.title}")
                continue
            seen.add(key)
            result.append(paper)
        return cls(result, warnings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "paper_count": len(self.papers),
            "warning_count": len(self.warnings),
            "warnings": self.warnings,
            "papers": [paper.to_dict() for paper in self.papers],
        }
