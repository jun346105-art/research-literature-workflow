from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_eval_run_manifest(
    out: Path,
    *,
    run_id: str,
    model: str = "",
    prompt_version: str = "",
    chunk_config: str = "",
    input_count: int = 0,
    success_count: int = 0,
    strict_evidence_failures: int = 0,
) -> dict[str, Any]:
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_version": prompt_version,
        "chunk_config": chunk_config,
        "metrics": {
            "input_count": input_count,
            "success_count": success_count,
            "strict_evidence_failures": strict_evidence_failures,
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def compare_evidence_notes(baseline_note: Path, proposed_note: Path, clean_context: Path, out: Path) -> dict[str, Any]:
    chunks = _chunks_by_id(json.loads(clean_context.read_text(encoding="utf-8-sig")))
    report = {
        "baseline": _score_note(json.loads(baseline_note.read_text(encoding="utf-8-sig")), chunks),
        "proposed": _score_note(json.loads(proposed_note.read_text(encoding="utf-8-sig")), chunks),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def score_evidence_note(note: dict[str, Any], clean_context: dict[str, Any]) -> dict[str, Any]:
    """Score exact evidence grounding without changing the supplied note."""
    return _score_note(note, _chunks_by_id(clean_context))


def _chunks_by_id(clean_context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {chunk["chunk_id"]: chunk for chunk in clean_context.get("chunks", [])}


def _score_note(note: dict[str, Any], chunks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures = []
    links = note.get("evidence_links", [])
    for index, link in enumerate(links, 1):
        failure = _evidence_failure(link, chunks)
        if failure:
            failures.append({"index": index, "type": failure, "chunk_id": link.get("chunk_id", "")})
    passed = len(links) - len(failures)
    return {
        "evidence_links_count": len(links),
        "pass_count": passed,
        "failure_count": len(failures),
        "exact_grounding_rate": passed / len(links) if links else 0,
        "failures": failures,
    }


def _evidence_failure(link: dict[str, Any], chunks: dict[str, dict[str, Any]]) -> str | None:
    chunk = chunks.get(link.get("chunk_id"))
    if not chunk:
        return "chunk_id_not_found"
    if link.get("page_start") != chunk.get("page_start") or link.get("page_end") != chunk.get("page_end"):
        return "page_range_mismatch"
    if link.get("evidence_text", "") not in chunk.get("text", ""):
        return "evidence_text_not_found"
    return None
