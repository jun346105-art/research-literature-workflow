from __future__ import annotations

import re

from litflow.context.models import CleanPage


def clean_page_text(page: dict) -> CleanPage:
    original = page.get("text") or ""
    text = original.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return CleanPage(
        page_number=int(page.get("page_number") or 0),
        text=text,
        original_char_count=len(original),
        cleaned_char_count=len(text),
    )


def clean_pages(pages: list[dict]) -> tuple[list[CleanPage], dict]:
    cleaned = [clean_page_text(page) for page in pages]
    return cleaned, {
        "original_char_count": sum(page.original_char_count for page in cleaned),
        "cleaned_char_count": sum(page.cleaned_char_count for page in cleaned),
        "page_count": len(cleaned),
        "warnings": [],
    }

