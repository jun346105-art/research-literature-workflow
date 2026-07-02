from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str
    char_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "text": self.text,
            "char_count": self.char_count,
        }


@dataclass(frozen=True)
class PdfTextExtraction:
    extractor: str = "pypdf"
    page_count: int = 0
    char_count: int = 0
    pages: list[PdfPageText] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "extractor": self.extractor,
            "page_count": self.page_count,
            "char_count": self.char_count,
            "pages": [page.to_dict() for page in self.pages],
            "warnings": self.warnings,
            "errors": self.errors,
        }

