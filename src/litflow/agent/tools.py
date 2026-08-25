from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentToolError(ValueError):
    pass


class ListPapersArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["zh", "en", "mixed"] | None = None
    title_keyword: str | None = Field(default=None, max_length=120)
    year: int | None = Field(default=None, ge=1900, le=2100)


class RetrieveEvidenceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=10)


class InspectPassagesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passage_ids: list[str] = Field(min_length=1, max_length=3)


class AnswerGroundedArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_id: str = Field(min_length=1, max_length=80)


class QueryEvidenceMatrixArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str | None = Field(default=None, max_length=200)
    paper_keys: list[str] = Field(default_factory=list, max_length=10)
    categories: list[str] = Field(default_factory=list, max_length=10)


class StageWritingDraftArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_ids: list[str] = Field(min_length=1, max_length=20)


TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "list_papers": ListPapersArgs,
    "retrieve_evidence": RetrieveEvidenceArgs,
    "inspect_passages": InspectPassagesArgs,
    "answer_grounded": AnswerGroundedArgs,
    "query_evidence_matrix": QueryEvidenceMatrixArgs,
    "stage_writing_draft": StageWritingDraftArgs,
}
TOOL_PERMISSIONS = {
    "list_papers": "read_only",
    "retrieve_evidence": "read_only",
    "inspect_passages": "read_only",
    "answer_grounded": "read_only_model_call",
    "query_evidence_matrix": "read_only",
    "stage_writing_draft": "approval_required",
}


def canonical_tool_signature(name: str, args: dict[str, Any]) -> str:
    return name + ":" + json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_tool_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    schema = TOOL_SCHEMAS.get(name)
    if schema is None:
        raise AgentToolError("tool_not_allowed")
    try:
        return schema.model_validate(args).model_dump(exclude_none=True)
    except Exception as exc:
        raise AgentToolError("tool_arguments_invalid") from exc


@dataclass
class FakeAgentTools:
    """Fake M8A core tools. They expose no qrels, gold, paths, or network."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"tool_name": name, "args": args})
        if name == "list_papers":
            return {"papers": [{"paper_key": "P1", "title": "Fixture Paper", "citation_key": "fixture2026", "language": "en", "year": 2026}]}
        if name == "retrieve_evidence":
            return {"passages": [{"passage_id": "P1:C1", "paper_key": "P1", "title": "Fixture Paper", "page_start": 1, "page_end": 1, "score": 1.0, "snippet": "Fixture evidence snippet."}], "evidence_refs": ["P1:C1"]}
        if name == "inspect_passages":
            return {"passages": [{"passage_id": item, "paper_key": "P1", "page_start": 1, "page_end": 1, "text": "Fixture complete passage.", "text_sha256": "fixture-sha"} for item in args["passage_ids"]]}
        if name == "answer_grounded":
            return {"final_status": "complete", "coverage_status": "complete", "verified_claim_ids": ["C1"], "evidence_refs": ["P1:C1"], "displayed_citation_validity": True, "displayed_quote_grounding": True, "displayed_claim_coverage": True}
        if name == "query_evidence_matrix":
            return {"record_ids": ["R1"], "records": [{"evidence_record_id": "R1", "review_decision": "pass"}]}
        if name == "stage_writing_draft":
            return {"artifact": "staged_writing_draft.json", "record_ids": args["record_ids"]}
        raise AgentToolError("tool_not_allowed")
