from __future__ import annotations

import re

from litflow.context.models import CleanPage

SECTION_PATTERNS = [
    ("abstract", r"^\s*abstract\b"),
    ("introduction", r"^\s*(\d+\.?\s*)?introduction\b"),
    ("related_work", r"^\s*(\d+\.?\s*)?(related work|literature review)\b"),
    ("background", r"^\s*(\d+\.?\s*)?background\b"),
    ("method", r"^\s*(\d+\.?\s*)?(method|methodology|approach|model)\b"),
    ("experiment", r"^\s*(\d+\.?\s*)?(experiment|experiments|experimental setup)\b"),
    ("results", r"^\s*(\d+\.?\s*)?results\b"),
    ("discussion", r"^\s*(\d+\.?\s*)?discussion\b"),
    ("conclusion", r"^\s*(\d+\.?\s*)?(conclusion|conclusions)\b"),
    ("references", r"^\s*(references|bibliography)\b"),
]


def guess_section(text: str) -> tuple[str, str]:
    for line in text.splitlines()[:20]:
        heading = line.strip()
        if not heading:
            continue
        for section, pattern in SECTION_PATTERNS:
            if re.search(pattern, heading, flags=re.IGNORECASE):
                return section, heading
    return "unknown", ""


def detect_sections(pages: list[CleanPage]) -> tuple[list[CleanPage], list[dict]]:
    current = "unknown"
    current_heading = ""
    section_rows: list[dict] = []
    result: list[CleanPage] = []
    for page in pages:
        guessed, heading = guess_section(page.text)
        if guessed != "unknown":
            current = guessed
            current_heading = heading
            section_rows.append(
                {
                    "section_guess": current,
                    "page_start": page.page_number,
                    "page_end": page.page_number,
                    "heading_text": heading,
                }
            )
        elif section_rows:
            section_rows[-1]["page_end"] = page.page_number
        result.append(page.model_copy(update={"section_guess": current}))
    return result, section_rows
