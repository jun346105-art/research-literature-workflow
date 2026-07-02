from __future__ import annotations

from pydantic import BaseModel, Field


class CleanPage(BaseModel):
    page_number: int
    text: str
    original_char_count: int
    cleaned_char_count: int
    section_guess: str = "unknown"


class TextChunk(BaseModel):
    chunk_id: str
    zotero_key: str
    citation_key: str | None
    title: str
    text: str
    char_count: int
    page_start: int
    page_end: int
    section_guess: str
    source_page_numbers: list[int]
    contains_annotation: bool = False
    annotation_ids: list[str] = Field(default_factory=list)

