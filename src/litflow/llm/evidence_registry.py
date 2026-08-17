from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from litflow.llm.deep_reading_models import EvidenceRecord
from litflow.llm.span_mapping import map_verbatim_span


class EvidenceRegistryError(ValueError):
    pass


class EvidenceRegistry:
    def __init__(self, zotero_key: str, chunks: list[dict[str, Any],], records: list[EvidenceRecord]) -> None:
        self.zotero_key = zotero_key
        self.chunks = {chunk["chunk_id"]: chunk for chunk in chunks}
        self.records = records

    def add_quote(self, chunk_id: str, quote_hint: str) -> tuple[str | None, str | None]:
        chunk = self.chunks.get(chunk_id)
        if not chunk:
            return None, "declared_chunk_missing"
        mapped = map_verbatim_span(quote_hint, chunk.get("text") or "")
        if mapped.status != "ok":
            return None, mapped.error_type
        evidence_id = f"{self.zotero_key}_deep_ev_{sum(record.origin == 'deep_quote' for record in self.records) + 1:04d}"
        self.records.append(_record(evidence_id, "deep_quote", chunk, mapped.start, mapped.end, mapped.evidence_text, mapped.method))
        return evidence_id, None


def load_registry(candidate_bank_path: Path, clean_context_path: Path) -> EvidenceRegistry:
    import json

    bank = json.loads(candidate_bank_path.read_text(encoding="utf-8-sig"))
    clean = json.loads(clean_context_path.read_text(encoding="utf-8-sig"))
    metadata = clean.get("metadata", {})
    zotero_key = metadata.get("zotero_key") or bank.get("metadata", {}).get("zotero_key")
    if not zotero_key:
        raise EvidenceRegistryError("zotero_key is missing from clean context")
    chunks = clean.get("chunks", [])
    by_chunk = {chunk["chunk_id"]: chunk for chunk in chunks}
    records: list[EvidenceRecord] = []
    for index, candidate in enumerate(bank.get("candidates", []), 1):
        chunk = by_chunk.get(candidate.get("chunk_id"))
        if not chunk:
            raise EvidenceRegistryError("candidate references missing chunk")
        mapped = map_verbatim_span(candidate.get("evidence_text") or "", chunk.get("text") or "")
        if mapped.status != "ok":
            raise EvidenceRegistryError("existing candidate evidence cannot be re-located")
        records.append(_record(f"{zotero_key}_ev_{index:04d}", "existing_candidate", chunk, mapped.start, mapped.end, mapped.evidence_text, candidate.get("anchoring_method") or mapped.method))
    return EvidenceRegistry(zotero_key, chunks, records)


def _record(evidence_id: str, origin: str, chunk: dict[str, Any], start: int | None, end: int | None, text: str, method: str) -> EvidenceRecord:
    if start is None or end is None:
        raise EvidenceRegistryError("mapped evidence has no span")
    return EvidenceRecord(
        evidence_id=evidence_id,
        origin=origin,
        chunk_id=chunk["chunk_id"],
        page_start=chunk["page_start"],
        page_end=chunk["page_end"],
        span_start=start,
        span_end=end,
        evidence_text=text,
        evidence_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        anchor_method=method,
    )
