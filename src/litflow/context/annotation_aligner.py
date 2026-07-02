from __future__ import annotations

from litflow.context.models import CleanPage, TextChunk


def align_annotations(notes: dict, pages: list[CleanPage], chunks: list[TextChunk]) -> tuple[dict, list[TextChunk]]:
    aligned_items = []
    chunk_annotation_ids: dict[str, list[str]] = {chunk.chunk_id: [] for chunk in chunks}
    for index, item in enumerate(notes.get("items", []), start=1):
        annotation_id = f"ann_{index:04d}"
        aligned = _align_one(annotation_id, item, pages, chunks)
        aligned_items.append(aligned)
        if aligned.get("matched_chunk_id"):
            chunk_annotation_ids.setdefault(aligned["matched_chunk_id"], []).append(annotation_id)

    updated_chunks = [
        chunk.model_copy(
            update={
                "contains_annotation": bool(chunk_annotation_ids.get(chunk.chunk_id)),
                "annotation_ids": chunk_annotation_ids.get(chunk.chunk_id, []),
            }
        )
        for chunk in chunks
    ]
    aligned_count = sum(1 for item in aligned_items if item["alignment_status"] in {"matched", "page_only", "chunk_only", "global_note"})
    return {
        "aligned_count": aligned_count,
        "unaligned_count": len(aligned_items) - aligned_count,
        "items": aligned_items,
    }, updated_chunks


def _align_one(annotation_id: str, item: dict, pages: list[CleanPage], chunks: list[TextChunk]) -> dict:
    text = item.get("text") or ""
    if item.get("type") == "note" and not item.get("page_label"):
        status = "global_note"
        matched_page = None
        matched_chunk_id = None
    else:
        matched_page = _find_page(text, pages)
        matched_chunk_id = _find_chunk(text, chunks)
        if matched_page and matched_chunk_id:
            status = "matched"
        elif matched_page:
            status = "page_only"
        elif matched_chunk_id:
            status = "chunk_only"
        else:
            status = "unaligned"
    return {
        "annotation_id": annotation_id,
        "type": item.get("type") or "",
        "text": text,
        "comment": item.get("comment") or "",
        "page_label": item.get("page_label") or "",
        "color": item.get("color") or "",
        "date_modified": item.get("date_modified") or "",
        "matched_page": matched_page,
        "matched_chunk_id": matched_chunk_id,
        "alignment_status": status,
    }


def _find_page(text: str, pages: list[CleanPage]) -> int | None:
    needle = _norm(text)
    if not needle:
        return None
    for page in pages:
        if needle in _norm(page.text):
            return page.page_number
    return None


def _find_chunk(text: str, chunks: list[TextChunk]) -> str | None:
    needle = _norm(text)
    if not needle:
        return None
    for chunk in chunks:
        if needle in _norm(chunk.text):
            return chunk.chunk_id
    return None


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())
