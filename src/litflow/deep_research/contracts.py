"""Versioned, offline DeepResearch domain contracts and bundle invariants."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .identity import ID_PREFIXES, make_stable_id


CONTRACT_VERSION = "dr-contracts-v1"
_ID_PATTERN = re.compile(r"^dr-([a-z]+)-[0-9a-f]{24}$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_LOCALE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
_PRIVATE_PATH_PATTERN = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")


class BriefApprovalStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class SourceKind(str, Enum):
    local_pdf = "local_pdf"
    passage_corpus = "passage_corpus"
    web = "web"


class EvidenceModality(str, Enum):
    text = "text"
    image_region = "image_region"
    table_region = "table_region"


class CitationRelation(str, Enum):
    support = "support"
    contradict = "contradict"
    context = "context"


class ContractModel(BaseModel):
    """Strict immutable base for durable contract facts."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    contract_version: Literal[CONTRACT_VERSION] = Field(default=CONTRACT_VERSION, description="Stable DeepResearch contract version.")


def _require_id(value: str, expected_kind: str) -> str:
    match = _ID_PATTERN.fullmatch(value)
    if match is None or match.group(1) != expected_kind:
        raise ValueError(f"{expected_kind}_id must be a deterministic DeepResearch ID")
    return value


def _require_hash(value: str) -> str:
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError("content_sha256 must be a lowercase 64-character SHA-256 hex digest")
    return value


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError("datetime must be UTC")
    return value.astimezone(UTC)


class ResearchTask(ContractModel):
    """User-scoped research task; execution state is intentionally absent."""

    task_id: str = Field(description="Program-generated deterministic task ID.")
    original_question: str = Field(min_length=1, description="Original user research question.")
    locale: str = Field(description="BCP-47-like task locale.")
    created_at: datetime = Field(description="Timezone-aware UTC task creation time.")
    constraints: tuple[str, ...] = Field(default=(), description="User-provided research boundaries.")
    deliverable_type: str = Field(min_length=1, description="Requested deliverable category.")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        return _require_id(value, "task")

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: str) -> str:
        if _LOCALE_PATTERN.fullmatch(value) is None:
            raise ValueError("locale must be a nonempty language or language-region tag")
        return value

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @classmethod
    def create(cls, original_question: str, locale: str, constraints: tuple[str, ...], deliverable_type: str, created_at: datetime) -> "ResearchTask":
        task_id = make_stable_id("task", {"original_question": original_question.strip(), "locale": locale.strip(), "constraints": list(constraints), "deliverable_type": deliverable_type.strip()})
        return cls(task_id=task_id, original_question=original_question, locale=locale, constraints=constraints, deliverable_type=deliverable_type, created_at=created_at)


class ResearchBrief(ContractModel):
    """Versioned brief whose execution approval is represented separately."""

    brief_id: str = Field(description="Program-generated deterministic brief ID.")
    task_id: str = Field(description="Owning task ID.")
    objective: str = Field(min_length=1, description="Research objective.")
    scope_inclusions: tuple[str, ...] = Field(default=(), description="Explicit in-scope items.")
    scope_exclusions: tuple[str, ...] = Field(default=(), description="Explicit excluded items.")
    deliverable: str = Field(min_length=1, description="Expected brief deliverable.")
    success_criteria: tuple[str, ...] = Field(default=(), description="Observable brief success criteria.")
    constraints: tuple[str, ...] = Field(default=(), description="Additional execution constraints.")
    approval_status: BriefApprovalStatus = Field(description="Current auditable approval state.")

    @field_validator("brief_id")
    @classmethod
    def validate_brief_id(cls, value: str) -> str:
        return _require_id(value, "brief")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        return _require_id(value, "task")

    @classmethod
    def create(cls, task_id: str, objective: str, scope_inclusions: tuple[str, ...], scope_exclusions: tuple[str, ...], deliverable: str, success_criteria: tuple[str, ...], constraints: tuple[str, ...], approval_status: BriefApprovalStatus) -> "ResearchBrief":
        brief_id = make_stable_id("brief", {"task_id": task_id, "objective": objective.strip(), "scope_inclusions": list(scope_inclusions), "scope_exclusions": list(scope_exclusions), "deliverable": deliverable.strip(), "success_criteria": list(success_criteria), "constraints": list(constraints)})
        return cls(brief_id=brief_id, task_id=task_id, objective=objective, scope_inclusions=scope_inclusions, scope_exclusions=scope_exclusions, deliverable=deliverable, success_criteria=success_criteria, constraints=constraints, approval_status=approval_status)


class BriefApproval(ContractModel):
    """Auditable approval event without a runtime boolean shortcut."""

    approval_id: str = Field(description="Program-generated deterministic approval record ID.")
    brief_id: str = Field(description="Approved or rejected brief ID.")
    task_id: str = Field(description="Owning task ID.")
    status: BriefApprovalStatus = Field(description="Recorded approval decision.")
    actor: str = Field(min_length=1, description="Human decision maker identifier.")
    decided_at: datetime = Field(description="Timezone-aware UTC decision time.")
    reason: str | None = Field(default=None, description="Optional decision rationale.")

    @field_validator("approval_id")
    @classmethod
    def validate_approval_id(cls, value: str) -> str:
        return _require_id(value, "approval")

    @field_validator("brief_id")
    @classmethod
    def validate_brief_id(cls, value: str) -> str:
        return _require_id(value, "brief")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        return _require_id(value, "task")

    @field_validator("decided_at")
    @classmethod
    def validate_decided_at(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @classmethod
    def create(cls, brief_id: str, task_id: str, status: BriefApprovalStatus, actor: str, decided_at: datetime, reason: str | None = None) -> "BriefApproval":
        approval_id = make_stable_id("approval", {"brief_id": brief_id, "task_id": task_id, "status": status.value, "actor": actor.strip(), "decided_at": decided_at.isoformat(), "reason": reason.strip() if reason else None})
        return cls(approval_id=approval_id, brief_id=brief_id, task_id=task_id, status=status, actor=actor, decided_at=decided_at, reason=reason)


class ResearchSubtask(ContractModel):
    """Task-local research question with declarative DAG dependencies only."""

    subtask_id: str = Field(description="Program-generated deterministic subtask ID.")
    task_id: str = Field(description="Owning task ID.")
    question: str = Field(min_length=1, description="Subtask research question.")
    rationale: str = Field(min_length=1, description="Why the subtask is needed.")
    dependency_ids: tuple[str, ...] = Field(default=(), description="Required predecessor subtask IDs.")
    expected_evidence: tuple[str, ...] = Field(default=(), description="Expected evidence categories.")
    completion_criteria: tuple[str, ...] = Field(default=(), description="Observable subtask completion criteria.")

    @field_validator("subtask_id")
    @classmethod
    def validate_subtask_id(cls, value: str) -> str:
        return _require_id(value, "subtask")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        return _require_id(value, "task")

    @field_validator("dependency_ids")
    @classmethod
    def validate_dependency_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("dependency_ids must be unique")
        return tuple(_require_id(value, "subtask") for value in values)

    @classmethod
    def create(cls, task_id: str, question: str, rationale: str, dependency_ids: tuple[str, ...] = (), expected_evidence: tuple[str, ...] = (), completion_criteria: tuple[str, ...] = ()) -> "ResearchSubtask":
        subtask_id = make_stable_id("subtask", {"task_id": task_id, "question": question.strip(), "rationale": rationale.strip(), "dependency_ids": list(dependency_ids), "expected_evidence": list(expected_evidence), "completion_criteria": list(completion_criteria)})
        return cls(subtask_id=subtask_id, task_id=task_id, question=question, rationale=rationale, dependency_ids=dependency_ids, expected_evidence=expected_evidence, completion_criteria=completion_criteria)


class Source(ContractModel):
    """Portable source identity without a private filesystem path."""

    source_id: str = Field(description="Program-generated deterministic source ID.")
    kind: SourceKind = Field(description="Source category; Web is contract-only in B01.")
    canonical_reference: str = Field(min_length=1, description="Portable DOI, URL, paper key or content reference.")
    title: str = Field(min_length=1, description="Source title.")
    content_sha256: str = Field(description="SHA-256 identity of source content.")
    language: str = Field(description="Source language tag.")
    published_at: datetime | None = Field(default=None, description="Optional timezone-aware UTC publication time.")
    bibliographic_metadata: dict[str, str] = Field(default_factory=dict, description="Controlled portable bibliographic fields.")

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _require_id(value, "source")

    @field_validator("content_sha256")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        return _require_hash(value)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if _LOCALE_PATTERN.fullmatch(value) is None:
            raise ValueError("language must be a nonempty language or language-region tag")
        return value

    @field_validator("canonical_reference")
    @classmethod
    def reject_private_path(cls, value: str) -> str:
        if _PRIVATE_PATH_PATTERN.match(value):
            raise ValueError("canonical_reference cannot be a private absolute path")
        return value

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime | None) -> datetime | None:
        return _require_utc(value) if value is not None else None

    @field_validator("bibliographic_metadata")
    @classmethod
    def reject_private_metadata_paths(cls, value: dict[str, str]) -> dict[str, str]:
        if any(_PRIVATE_PATH_PATTERN.match(item) for item in value.values()):
            raise ValueError("bibliographic metadata cannot contain private absolute paths")
        return value

    @classmethod
    def create(cls, kind: SourceKind, canonical_reference: str, title: str, content_sha256: str, language: str, published_at: datetime | None = None, bibliographic_metadata: dict[str, str] | None = None) -> "Source":
        metadata = bibliographic_metadata or {}
        source_id = make_stable_id("source", {"kind": kind.value, "canonical_reference": canonical_reference.strip(), "content_sha256": content_sha256, "language": language.strip()})
        return cls(source_id=source_id, kind=kind, canonical_reference=canonical_reference, title=title, content_sha256=content_sha256, language=language, published_at=published_at, bibliographic_metadata=metadata)


class EvidenceLocator(ContractModel):
    """Locator for current text and future page-region evidence without extraction code."""

    passage_id: str | None = Field(default=None, description="Optional stable passage or chunk identity.")
    page_number: int | None = Field(default=None, ge=1, description="Optional one-based source page number.")
    span_start: int | None = Field(default=None, ge=0, description="Optional inclusive text span start.")
    span_end: int | None = Field(default=None, ge=0, description="Optional exclusive text span end.")
    bbox: tuple[float, float, float, float] | None = Field(default=None, description="Optional planned region coordinates x0,y0,x1,y1.")
    coordinate_space: str | None = Field(default=None, description="Coordinate-space name required with bbox.")

    @model_validator(mode="after")
    def validate_locator_shape(self) -> "EvidenceLocator":
        if (self.span_start is None) != (self.span_end is None):
            raise ValueError("span_start and span_end must appear together")
        if self.span_start is not None and self.span_end is not None and self.span_end <= self.span_start:
            raise ValueError("span_end must be greater than span_start")
        if (self.bbox is None) != (self.coordinate_space is None):
            raise ValueError("bbox and coordinate_space must appear together")
        if self.bbox is not None:
            if self.page_number is None or not all(math.isfinite(value) for value in self.bbox) or self.bbox[2] <= self.bbox[0] or self.bbox[3] <= self.bbox[1]:
                raise ValueError("bbox requires page number, finite coordinates, and positive area")
        return self

    def validate_for_modality(self, modality: EvidenceModality) -> None:
        if modality is EvidenceModality.text and (not self.passage_id or self.bbox is not None or self.coordinate_space is not None):
            raise ValueError("text modality requires passage_id and forbids bbox")
        if modality in {EvidenceModality.image_region, EvidenceModality.table_region} and (self.bbox is None or self.coordinate_space is None or self.page_number is None or self.span_start is not None):
            raise ValueError("region modality requires page bbox and forbids text span")


class EvidenceUnit(ContractModel):
    """Verbatim, groundable evidence; derived interpretation belongs in Claim."""

    evidence_id: str = Field(description="Program-generated deterministic evidence ID.")
    source_id: str = Field(description="Referenced source ID.")
    modality: EvidenceModality = Field(description="Evidence modality; regions are planned contract support.")
    locator: EvidenceLocator = Field(description="Evidence location in the source.")
    verbatim_content: str = Field(min_length=1, description="Verbatim groundable evidence content.")
    content_sha256: str = Field(description="SHA-256 of verbatim content.")
    language: str = Field(description="Evidence language tag.")
    provenance_metadata: dict[str, str] = Field(default_factory=dict, description="Controlled provenance metadata without private paths.")

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        return _require_id(value, "evidence")

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _require_id(value, "source")

    @field_validator("content_sha256")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        return _require_hash(value)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if _LOCALE_PATTERN.fullmatch(value) is None:
            raise ValueError("language must be a nonempty language or language-region tag")
        return value

    @model_validator(mode="after")
    def validate_evidence(self) -> "EvidenceUnit":
        self.locator.validate_for_modality(self.modality)
        if hashlib.sha256(self.verbatim_content.encode("utf-8")).hexdigest() != self.content_sha256:
            raise ValueError("content_sha256 does not match verbatim_content")
        if any(_PRIVATE_PATH_PATTERN.match(item) for item in self.provenance_metadata.values()):
            raise ValueError("provenance metadata cannot contain private absolute paths")
        return self

    @classmethod
    def create(cls, source_id: str, modality: EvidenceModality, locator: EvidenceLocator, verbatim_content: str, language: str, provenance_metadata: dict[str, str] | None = None) -> "EvidenceUnit":
        content = verbatim_content.strip()
        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        evidence_id = make_stable_id("evidence", {"source_id": source_id, "modality": modality.value, "locator": locator.model_dump(mode="json"), "content_sha256": content_sha256, "language": language.strip()})
        return cls(evidence_id=evidence_id, source_id=source_id, modality=modality, locator=locator, verbatim_content=content, content_sha256=content_sha256, language=language, provenance_metadata=provenance_metadata or {})


class Claim(ContractModel):
    """Task-local assertion without embedded citation objects or validation status."""

    claim_id: str = Field(description="Program-generated deterministic claim ID.")
    task_id: str = Field(description="Owning task ID.")
    text: str = Field(min_length=1, description="Claim text.")
    language: str = Field(description="Claim language tag.")
    claim_type: str | None = Field(default=None, description="Optional claim category.")
    entities: tuple[str, ...] = Field(default=(), description="Optional referenced entity labels.")

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        return _require_id(value, "claim")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        return _require_id(value, "task")

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if _LOCALE_PATTERN.fullmatch(value) is None:
            raise ValueError("language must be a nonempty language or language-region tag")
        return value

    @classmethod
    def create(cls, task_id: str, text: str, language: str, claim_type: str | None = None, entities: tuple[str, ...] = ()) -> "Claim":
        claim_id = make_stable_id("claim", {"task_id": task_id, "text": text.strip(), "language": language.strip(), "claim_type": claim_type.strip() if claim_type else None, "entities": list(entities)})
        return cls(claim_id=claim_id, task_id=task_id, text=text, language=language, claim_type=claim_type, entities=entities)


class Citation(ContractModel):
    """Reference from a claim to existing evidence; semantic validity is later work."""

    citation_id: str = Field(description="Program-generated deterministic citation ID.")
    claim_id: str = Field(description="Referenced claim ID.")
    evidence_id: str = Field(description="Referenced evidence ID.")
    relation: CitationRelation = Field(description="Declared evidence relation.")
    quote: str | None = Field(default=None, description="Optional verbatim quote from the evidence content.")
    quote_span_start: int | None = Field(default=None, ge=0, description="Optional inclusive quote span start.")
    quote_span_end: int | None = Field(default=None, ge=0, description="Optional exclusive quote span end.")

    @field_validator("citation_id")
    @classmethod
    def validate_citation_id(cls, value: str) -> str:
        return _require_id(value, "citation")

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, value: str) -> str:
        return _require_id(value, "claim")

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value: str) -> str:
        return _require_id(value, "evidence")

    @model_validator(mode="after")
    def validate_quote_shape(self) -> "Citation":
        start_missing = self.quote_span_start is None
        end_missing = self.quote_span_end is None
        if start_missing != end_missing:
            raise ValueError("quote span start and end must appear together")
        has_span = not start_missing
        if self.quote is None and has_span:
            raise ValueError("quote is required when quote span is present")
        if self.quote is not None and not has_span:
            raise ValueError("quote requires quote span")
        if self.quote_span_start is not None and self.quote_span_end is not None and self.quote_span_end <= self.quote_span_start:
            raise ValueError("quote span end must be greater than quote span start")
        return self

    @classmethod
    def create(cls, claim_id: str, evidence_id: str, relation: CitationRelation, quote: str | None = None, quote_span_start: int | None = None, quote_span_end: int | None = None) -> "Citation":
        citation_id = make_stable_id("citation", {"claim_id": claim_id, "evidence_id": evidence_id, "relation": relation.value, "quote": quote.strip() if quote else None, "quote_span_start": quote_span_start, "quote_span_end": quote_span_end})
        return cls(citation_id=citation_id, claim_id=claim_id, evidence_id=evidence_id, relation=relation, quote=quote, quote_span_start=quote_span_start, quote_span_end=quote_span_end)


class ContractBundle(ContractModel):
    """Cross-object validation boundary for a single task contract graph."""

    task: ResearchTask = Field(description="Single owning research task.")
    brief: ResearchBrief = Field(description="Task research brief.")
    brief_approvals: tuple[BriefApproval, ...] = Field(default=(), description="Auditable brief decisions.")
    subtasks: tuple[ResearchSubtask, ...] = Field(default=(), description="Task-local dependency DAG.")
    sources: tuple[Source, ...] = Field(default=(), description="Known portable sources.")
    evidence_units: tuple[EvidenceUnit, ...] = Field(default=(), description="Groundable evidence units.")
    claims: tuple[Claim, ...] = Field(default=(), description="Task-local claims.")
    citations: tuple[Citation, ...] = Field(default=(), description="Claim to evidence references.")

    @model_validator(mode="after")
    def validate_bundle(self) -> "ContractBundle":
        if self.brief.task_id != self.task.task_id:
            raise ValueError("brief must belong to the same task")
        self._validate_unique("subtask", self.subtasks, "subtask_id")
        self._validate_unique("source", self.sources, "source_id")
        self._validate_unique("evidence", self.evidence_units, "evidence_id")
        self._validate_unique("claim", self.claims, "claim_id")
        self._validate_unique("citation", self.citations, "citation_id")
        self._validate_approvals()
        claim_ids = {claim.claim_id for claim in self.claims}
        evidence_by_id = {evidence.evidence_id: evidence for evidence in self.evidence_units}
        for citation in self.citations:
            if citation.claim_id not in claim_ids:
                raise ValueError("citation references an unknown claim_id")
            if citation.evidence_id not in evidence_by_id:
                raise ValueError("citation references an unknown evidence_id")
            if citation.quote is not None:
                evidence = evidence_by_id[citation.evidence_id]
                assert citation.quote_span_start is not None and citation.quote_span_end is not None
                if citation.quote_span_end > len(evidence.verbatim_content) or evidence.verbatim_content[citation.quote_span_start:citation.quote_span_end] != citation.quote:
                    raise ValueError("citation quote/span does not match evidence content")
        source_ids = {source.source_id for source in self.sources}
        for evidence in self.evidence_units:
            if evidence.source_id not in source_ids:
                raise ValueError("evidence references an unknown source_id")
        for claim in self.claims:
            if claim.task_id != self.task.task_id:
                raise ValueError("claim must belong to the same task")
        self._validate_subtasks()
        return self

    @staticmethod
    def _validate_unique(kind: str, values: tuple[Any, ...], attribute: str) -> None:
        ids = [getattr(value, attribute) for value in values]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{kind} IDs must be unique")

    def _validate_approvals(self) -> None:
        approvals = [item for item in self.brief_approvals if item.brief_id == self.brief.brief_id and item.task_id == self.task.task_id]
        if self.brief.approval_status is not BriefApprovalStatus.draft and not any(item.status is self.brief.approval_status for item in approvals):
            raise ValueError("brief approval status requires a matching auditable approval record")
        if any(item.task_id != self.task.task_id or item.brief_id != self.brief.brief_id for item in self.brief_approvals):
            raise ValueError("brief approval must belong to the same task and brief")

    def _validate_subtasks(self) -> None:
        by_id = {subtask.subtask_id: subtask for subtask in self.subtasks}
        for subtask in self.subtasks:
            if subtask.task_id != self.task.task_id:
                raise ValueError("subtask must belong to the same task")
            for dependency_id in subtask.dependency_ids:
                if dependency_id == subtask.subtask_id:
                    raise ValueError("subtask cannot have a self dependency")
                if dependency_id not in by_id:
                    raise ValueError("subtask dependency references an unknown subtask")
        self.topological_subtask_ids()

    def topological_subtask_ids(self) -> tuple[str, ...]:
        by_id = {subtask.subtask_id: subtask for subtask in self.subtasks}
        remaining = {subtask_id: set(subtask.dependency_ids) for subtask_id, subtask in by_id.items()}
        ordered: list[str] = []
        while remaining:
            ready = sorted(subtask_id for subtask_id, dependencies in remaining.items() if not dependencies)
            if not ready:
                raise ValueError("subtask dependency cycle detected")
            for subtask_id in ready:
                ordered.append(subtask_id)
                remaining.pop(subtask_id)
            for dependencies in remaining.values():
                dependencies.difference_update(ready)
        return tuple(ordered)
