from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from litflow.llm.client import LLMClient, LLMError, OpenAICompatibleClient
from litflow.llm.models import StructuredReadingNote
from litflow.llm.prompts import build_structured_reading_prompt


class EvidenceValidationError(ValueError):
    def __init__(
        self,
        evidence_error_type: str,
        message: str,
        *,
        failed_chunk_id: str | None = None,
        candidate_chunk_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.evidence_error_type = evidence_error_type
        self.failed_chunk_id = failed_chunk_id
        self.candidate_chunk_id = candidate_chunk_id


def build_llm_input(clean_context: dict[str, Any], max_chunks: int | None = None) -> dict[str, Any]:
    chunks = clean_context.get("chunks", [])
    if max_chunks is not None:
        chunks = chunks[:max_chunks]
    return {
        "metadata": clean_context.get("metadata", {}),
        "chunks": [
            {
                "chunk_id": chunk.get("chunk_id"),
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "section_guess": chunk.get("section_guess"),
                "text": chunk.get("text"),
            }
            for chunk in chunks
        ],
        "annotations": clean_context.get("annotations", {}),
        "quality_warnings": clean_context.get("quality", {}).get("warnings", []),
    }


def read_paper_with_llm(
    clean_context_path: Path,
    output_path: Path,
    *,
    max_chunks: int | None = None,
    client: LLMClient | None = None,
) -> StructuredReadingNote:
    clean_context = json.loads(clean_context_path.read_text(encoding="utf-8-sig"))
    llm_input = build_llm_input(clean_context, max_chunks=max_chunks)
    prompt = build_structured_reading_prompt(llm_input)
    client = client or OpenAICompatibleClient.from_env()
    allowed_chunks = {chunk["chunk_id"]: chunk for chunk in llm_input["chunks"]}

    raw_response = ""
    current_prompt = prompt
    for attempt in range(2):
        raw_response = client.complete_json(current_prompt)
        try:
            data = _parse_json_response(raw_response)
            note = StructuredReadingNote.model_validate(data)
            _validate_evidence_links(note, allowed_chunks)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(note.model_dump_json(indent=2) + "\n", encoding="utf-8")
            return note
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            if attempt == 1:
                _write_error(output_path, raw_response, exc)
                raise LLMError(f"LLM returned invalid structured JSON; raw response saved to {output_path.with_suffix('.error.json')}")
            current_prompt = _retry_prompt(prompt, raw_response, exc)
    raise LLMError("unreachable")


def _validate_evidence_links(note: StructuredReadingNote, allowed_chunks: dict[str, dict]) -> None:
    for link in note.evidence_links:
        candidate_chunk_id = _find_chunk_containing_text(link.evidence_text, allowed_chunks)
        if link.chunk_id not in allowed_chunks:
            if candidate_chunk_id:
                raise EvidenceValidationError(
                    "wrong_chunk_id",
                    f"evidence text exists in {candidate_chunk_id}, not declared chunk_id: {link.chunk_id}",
                    failed_chunk_id=link.chunk_id,
                    candidate_chunk_id=candidate_chunk_id,
                )
            raise EvidenceValidationError(
                "evidence_text_not_found",
                f"evidence link references unknown chunk_id and text was not found: {link.chunk_id}",
                failed_chunk_id=link.chunk_id,
            )
        chunk = allowed_chunks[link.chunk_id]
        if link.page_start != chunk["page_start"] or link.page_end != chunk["page_end"]:
            raise EvidenceValidationError(
                "page_range_mismatch",
                f"evidence link page range does not match chunk_id: {link.chunk_id}",
                failed_chunk_id=link.chunk_id,
            )
        if link.evidence_text and link.evidence_text not in (chunk.get("text") or ""):
            if candidate_chunk_id:
                raise EvidenceValidationError(
                    "wrong_chunk_id",
                    f"evidence text exists in {candidate_chunk_id}, not declared chunk_id: {link.chunk_id}",
                    failed_chunk_id=link.chunk_id,
                    candidate_chunk_id=candidate_chunk_id,
                )
            raise EvidenceValidationError(
                "evidence_text_not_found",
                f"evidence text is not found in any chunk; declared chunk_id: {link.chunk_id}",
                failed_chunk_id=link.chunk_id,
            )


def _parse_json_response(raw_response: str) -> Any:
    text = raw_response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def _retry_prompt(prompt: str, raw_response: str, error: Exception | None = None) -> str:
    reason = f"\nValidation error: {_format_error_summary(error)}\n" if error else "\n"
    return (
        f"{prompt}\n\nYour previous response was not valid for the requested schema and evidence rules."
        f"{reason}"
        "Return corrected JSON only. If evidence_text failed, copy a short exact span from the cited chunk without fixing PDF artifacts.\n"
        "Previous response:\n"
        f"{raw_response}"
    )


def _write_error(output_path: Path, raw_response: str, error: Exception) -> None:
    error_path = output_path.with_suffix(".error.json")
    error_path.parent.mkdir(parents=True, exist_ok=True)
    error_path.write_text(
        json.dumps(
            {
                "error_type": type(error).__name__,
                "error": str(error),
                "evidence_error_type": getattr(error, "evidence_error_type", None),
                "failed_chunk_id": getattr(error, "failed_chunk_id", None),
                "candidate_chunk_id": getattr(error, "candidate_chunk_id", None),
                "raw_response": raw_response,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

def _find_chunk_containing_text(evidence_text: str, allowed_chunks: dict[str, dict]) -> str | None:
    if not evidence_text:
        return None
    for chunk_id, chunk in allowed_chunks.items():
        if evidence_text in (chunk.get("text") or ""):
            return chunk_id
    return None


def _format_error_summary(error: Exception | None) -> str:
    if not error:
        return ""
    if isinstance(error, EvidenceValidationError):
        parts = [f"evidence_error_type={error.evidence_error_type}", str(error)]
        if error.failed_chunk_id:
            parts.append(f"failed_chunk_id={error.failed_chunk_id}")
        if error.candidate_chunk_id:
            parts.append(f"candidate_chunk_id={error.candidate_chunk_id}")
        return "; ".join(parts)
    return str(error)
