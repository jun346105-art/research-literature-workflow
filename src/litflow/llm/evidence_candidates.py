from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from litflow.llm.client import LLMClient, OpenAICompatibleClient
from litflow.llm.structured_reader import _anchor_quote_hint, _parse_json_response


def build_evidence_candidate_bank(
    clean_context_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    client: LLMClient | None = None,
    research_context: str | None = None,
) -> dict[str, Any]:
    clean_context = json.loads(clean_context_path.read_text(encoding="utf-8-sig"))
    client = client or OpenAICompatibleClient.from_env()
    chunks = clean_context.get("chunks", [])
    candidates: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        page_start = chunk.get("page_start")
        page_end = chunk.get("page_end")
        text = chunk.get("text") or ""
        try:
            raw = client.complete_json(_chunk_prompt(chunk, research_context))
            data = _parse_json_response(raw)
            for item in data.get("candidates", [])[:2]:
                quote_hint = item.get("quote_hint", "")
                anchored = _anchor_quote_hint(quote_hint, text)
                base = {
                    "claim": item.get("claim", ""),
                    "evidence_type": item.get("evidence_type", "other"),
                    "quote_hint": quote_hint,
                    "chunk_id": chunk_id,
                    "page_start": page_start,
                    "page_end": page_end,
                }
                if anchored["status"] == "ok":
                    evidence_text = anchored["evidence_text"]
                    candidates.append(
                        {
                            **base,
                            "evidence_text": evidence_text,
                            "anchoring_method": anchored["method"],
                            "status": "anchored",
                        }
                    )
                else:
                    failures.append({**base, "status": "failed", **anchored})
        except Exception as exc:
            failures.append(
                {
                    "chunk_id": chunk_id,
                    "page_start": page_start,
                    "page_end": page_end,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    bank = {
        "metadata": {
            "source": str(clean_context_path),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "chunk_count": len(chunks),
            "llm_call_count": len(chunks),
            "candidate_count": len(candidates) + len(failures),
            "anchored_count": len(candidates),
            "failed_count": len(failures),
        },
        "candidates": candidates,
        "failures": failures,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "metadata": {**bank["metadata"], "output": str(output_path)},
        "success": len(candidates) >= 5 and all(c["evidence_text"] in _chunk_text(c["chunk_id"], chunks) for c in candidates),
        "failure_types": _counts(f.get("error_type", "other") for f in failures),
        "anchoring_methods": _counts(c.get("anchoring_method", "unknown") for c in candidates),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _chunk_prompt(chunk: dict[str, Any], research_context: str | None = None) -> str:
    payload = {
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "section_guess": chunk.get("section_guess"),
        "text": chunk.get("text"),
    }
    context_instruction = f"Research context for consistent evaluation: {research_context}\n" if research_context else ""
    return (
        "You extract evidence candidates from one paper chunk only.\n"
        "Return JSON only: {\"candidates\":[{\"claim\":\"\",\"quote_hint\":\"\",\"evidence_type\":\"background|method|experiment|result|limitation|other\"}]}.\n"
        "Return 0-2 candidates. Do not output chunk_id or page_start/page_end.\n"
        "quote_hint must come from this chunk only, be short, contiguous, and specific. If nothing useful, return an empty list.\n"
        "Do not use external knowledge. Do not invent.\n\n"
        f"{context_instruction}"
        f"Chunk:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _chunk_text(chunk_id: str, chunks: list[dict[str, Any]]) -> str:
    for chunk in chunks:
        if chunk.get("chunk_id") == chunk_id:
            return chunk.get("text") or ""
    return ""


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
