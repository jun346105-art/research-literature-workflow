from __future__ import annotations

from collections import Counter

from litflow.context.models import CleanPage, TextChunk


def chunk_pages(
    pages: list[CleanPage],
    *,
    zotero_key: str,
    citation_key: str | None,
    title: str,
    chunk_size_chars: int = 3500,
    chunk_overlap_chars: int = 400,
) -> list[TextChunk]:
    nonempty = [page for page in pages if page.text.strip()]
    if not nonempty:
        return []
    full_text, spans = _join_pages(nonempty)
    step = max(1, chunk_size_chars - chunk_overlap_chars)
    chunks: list[TextChunk] = []
    start = 0
    while start < len(full_text):
        end = min(len(full_text), start + chunk_size_chars)
        text = full_text[start:end].strip()
        if text:
            page_numbers = _pages_for_range(spans, start, end)
            section = _section_for_pages(nonempty, page_numbers)
            chunks.append(
                TextChunk(
                    chunk_id=f"{zotero_key}_chunk_{len(chunks) + 1:04d}",
                    zotero_key=zotero_key,
                    citation_key=citation_key,
                    title=title,
                    text=text,
                    char_count=len(text),
                    page_start=min(page_numbers),
                    page_end=max(page_numbers),
                    section_guess=section,
                    source_page_numbers=page_numbers,
                )
            )
        if end == len(full_text):
            break
        start += step
    return chunks


def _join_pages(pages: list[CleanPage]) -> tuple[str, list[tuple[int, int, int]]]:
    parts: list[str] = []
    spans: list[tuple[int, int, int]] = []
    pos = 0
    for page in pages:
        if parts:
            parts.append("\n\n")
            pos += 2
        start = pos
        parts.append(page.text)
        pos += len(page.text)
        spans.append((start, pos, page.page_number))
    return "".join(parts), spans


def _pages_for_range(spans: list[tuple[int, int, int]], start: int, end: int) -> list[int]:
    pages = [page for span_start, span_end, page in spans if span_start < end and span_end > start]
    return pages or [spans[0][2]]


def _section_for_pages(pages: list[CleanPage], page_numbers: list[int]) -> str:
    by_number = {page.page_number: page.section_guess for page in pages}
    counts = Counter(by_number.get(number, "unknown") for number in page_numbers)
    return counts.most_common(1)[0][0] if counts else "unknown"

