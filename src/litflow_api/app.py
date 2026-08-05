from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from litflow.llm.client import LLMError
from litflow.llm.evidence_bank_note import generate_note_from_evidence_bank
from litflow.llm.evidence_candidates import build_evidence_candidate_bank
from litflow.obsidian.update_preview import preview_obsidian_update

app = FastAPI(
    title="Research Literature Workflow API",
    version="0.1.1",
    description="Minimal API wrapper for safe litflow preview and anchored evidence workflows.",
)


class EvidenceCandidateBankRequest(BaseModel):
    clean_context: Path
    out: Path
    report: Path


class EvidenceBankNoteRequest(BaseModel):
    candidate_bank: Path
    clean_context: Path
    out: Path
    zotero_key: str
    citation_key: str
    title: str
    research_context: str | None = None


class PreviewRequest(BaseModel):
    structured_note: Path
    vault: Path
    inbox: str
    out: Path
    manifest: Path


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/evidence-candidate-bank")
def evidence_candidate_bank(request: EvidenceCandidateBankRequest) -> dict[str, Any]:
    try:
        report = build_evidence_candidate_bank(request.clean_context, request.out, request.report)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "success" if report.get("success") else "needs_review",
        "candidate_bank_path": str(request.out),
        "report_path": str(request.report),
        "metadata": report.get("metadata", {}),
        "failure_types": report.get("failure_types", {}),
        "anchoring_methods": report.get("anchoring_methods", {}),
    }


@app.post("/structured-note-from-bank")
def structured_note_from_bank(request: EvidenceBankNoteRequest) -> dict[str, Any]:
    try:
        note = generate_note_from_evidence_bank(
            request.candidate_bank,
            request.clean_context,
            request.out,
            zotero_key=request.zotero_key,
            citation_key=request.citation_key,
            title=request.title,
            research_context=request.research_context,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "success",
        "structured_note_path": str(request.out),
        "zotero_key": note.zotero_key,
        "citation_key": note.citation_key,
        "evidence_links_count": len(note.evidence_links),
    }


@app.post("/preview-obsidian-update")
def preview_update(request: PreviewRequest) -> dict[str, Any]:
    try:
        manifest = preview_obsidian_update(request.structured_note, request.vault, request.inbox, request.out, request.manifest)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    item = manifest["items"][0]
    return {
        "status": item["status"],
        "target_note_path": item["target_note_path"],
        "preview_path": item["preview_path"],
        "manifest_path": str(request.manifest),
        "warnings": item.get("warnings", []),
    }
