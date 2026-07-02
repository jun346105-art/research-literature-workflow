from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceLink(BaseModel):
    claim: str = ""
    chunk_id: str = ""
    page_start: int | None = None
    page_end: int | None = None
    evidence_text: str = ""


class StructuredReadingNote(BaseModel):
    zotero_key: str
    citation_key: str | None = None
    title: str = ""
    reading_status: str = "llm_draft"
    one_sentence_summary: str = ""
    research_background: str = ""
    research_gap: str = ""
    core_contribution: str = ""
    method_summary: str = ""
    data_or_experiment: str = ""
    model_or_algorithm: str = ""
    objective_or_task: str = ""
    key_results: str = ""
    limitations: str = ""
    relevance_to_my_research: str = ""
    usable_quotes_or_evidence: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    tags_suggestion: list[str] = Field(default_factory=list)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

