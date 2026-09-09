"""Offline single-writer boundary and deterministic evidence-grounded report validation."""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from litflow.llm.span_mapping import map_verbatim_span

from .budgets import BudgetLedger, BudgetSpec, TokenUsage
from .contracts import (
    BriefApproval,
    Citation,
    CitationRelation,
    Claim,
    ContractBundle,
    ContractModel,
    ResearchBrief,
    ResearchTask,
)
from .executor import EvidenceGraph
from .gap_replan import GapConflictAssessment
from .identity import canonical_json_bytes, make_stable_id, sha256_hex
from .operations import OperationKind, OperationStatus
from .planner import ValidatedResearchPlan, require_approved_brief
from .policies import CancellationToken
from .runtime_v2 import (
    GENESIS_HASH,
    CoordinatedCheckpointV2,
    RuntimeEventEnvelope,
    RuntimeEventType,
    UnifiedEventStore,
    create_runtime_event,
    reduce_runtime_events,
    replay_runtime_events,
    write_coordinated_checkpoint,
)
from .state import RunState, RunStatus, transition


WRITER_VERSION = "dr-single-writer-v1"
REPORT_DRAFT_VERSION = "dr-report-draft-v1"
VALIDATED_REPORT_VERSION = "dr-validated-report-v1"


class WriterError(ValueError):
    """Fail-closed writer boundary error without a provider fallback."""

    def __init__(self, code: str, message: str, diagnostics: dict[str, object] | None = None):
        self.code, self.diagnostics = code, diagnostics or {}
        super().__init__(f"{code}: {message}")


class ReportStatus(str, Enum):
    complete = "complete"
    partial = "partial"
    insufficient_evidence = "insufficient_evidence"
    manual_review_required = "manual_review_required"


class _DraftModel(BaseModel):
    """Untrusted writer data: strict scalar types, harmless unknown metadata ignored."""

    model_config = ConfigDict(extra="ignore", frozen=True, strict=True, str_strip_whitespace=True)


def _reject_fields(values: object, forbidden: frozenset[str]) -> object:
    if isinstance(values, dict) and forbidden.intersection(values):
        raise ValueError("writer draft attempts to own program-controlled data")
    return values


class CitationProposal(_DraftModel):
    evidence_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    relation: Literal["support", "contradict", "context"] = "support"

    @model_validator(mode="before")
    @classmethod
    def reject_formal_id(cls, values: object) -> object:
        return _reject_fields(values, frozenset({"citation_id", "source_id", "locator"}))


class ClaimProposal(_DraftModel):
    text: str = Field(min_length=1)
    language: str = Field(min_length=1)
    citations: list[CitationProposal] = Field(default_factory=list)
    claim_type: str | None = None
    entities: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_formal_id(cls, values: object) -> object:
        return _reject_fields(values, frozenset({"claim_id", "evidence_units", "final_answer"}))


class ReportSectionDraft(_DraftModel):
    heading: str = Field(min_length=1)
    claims: list[ClaimProposal] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_controlled_fields(cls, values: object) -> object:
        return _reject_fields(values, frozenset({"section_id", "claim_ids", "citation_ids"}))


class ConflictDisclosureDraft(_DraftModel):
    conflict_id: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=2)
    label: Literal["disputed", "uncertain"] = "disputed"


class ReportDraft(_DraftModel):
    """Candidate prose plus existing evidence references; it owns no formal identity."""

    schema_version: Literal[REPORT_DRAFT_VERSION] = REPORT_DRAFT_VERSION
    task_id: str = Field(min_length=1)
    brief_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    sections: list[ReportSectionDraft] = Field(min_length=1)
    abstention_reason: str | None = Field(default=None, min_length=1)
    conflict_disclosures: list[ConflictDisclosureDraft] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_graph_mutation(cls, values: object) -> object:
        return _reject_fields(values, frozenset({"evidence_graph", "evidence_units", "sources", "claims", "citations", "final_answer"}))


WRITER_OWNED_FIELDS = frozenset({"schema_version", "task_id", "brief_id", "plan_id", "run_id", "report_id", "claim_id", "citation_id"})


class WriterContentDraft(_DraftModel):
    """Untrusted model content; formal identity is injected by the program."""

    sections: list[ReportSectionDraft] = Field(min_length=1)
    abstention_reason: str | None = Field(default=None, min_length=1)
    conflict_disclosures: list[ConflictDisclosureDraft] = Field(default_factory=list)


def writer_validation_error_diagnostics(error: ValidationError) -> dict[str, object]:
    errors = error.errors(include_input=False)
    return {
        "failure_stage": "writer_schema",
        "contract_error_code": "writer_schema_invalid",
        "validation_errors_count": len(errors),
        "validation_errors": [
            {"type": str(item.get("type")), "location": ".".join(str(part) for part in item.get("loc", ())) or "root"}
            for item in errors[:16]
        ],
    }


def model_supplied_owned_fields(raw: object) -> tuple[str, ...]:
    payload = raw.model_dump(mode="json") if isinstance(raw, BaseModel) else raw
    found: set[str] = set()
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in WRITER_OWNED_FIELDS:
                    found.add(str(key))
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
    visit(payload)
    return tuple(sorted(found))


def finalize_writer_content_draft(raw: object, *, task: ResearchTask, brief: ResearchBrief, plan: ValidatedResearchPlan, graph: EvidenceGraph) -> ReportDraft:
    payload = raw.model_dump(mode="json") if isinstance(raw, BaseModel) else raw
    if not isinstance(payload, dict):
        raise WriterError("writer_schema_invalid", "Writer content draft must be an object", {"failure_stage": "writer_schema", "contract_error_code": "writer_schema_invalid", "observed_type": type(payload).__name__})
    owned = list(model_supplied_owned_fields(payload))
    content = {key: value for key, value in payload.items() if key not in WRITER_OWNED_FIELDS}
    try:
        draft = WriterContentDraft.model_validate(content)
    except ValidationError as error:
        raise WriterError("writer_schema_invalid", "Writer content draft failed schema validation", {**writer_validation_error_diagnostics(error), "model_supplied_owned_fields": owned}) from error
    return ReportDraft(schema_version=REPORT_DRAFT_VERSION, task_id=task.task_id, brief_id=brief.brief_id, plan_id=plan.plan_id, run_id=graph.run_id, sections=draft.sections, abstention_reason=draft.abstention_reason, conflict_disclosures=draft.conflict_disclosures)


class ReportValidationIssue(ContractModel):
    issue_id: str
    code: str = Field(min_length=1)
    severity: Literal["blocking", "warning"]
    section_heading: str | None = None
    claim_text_sha256: str | None = None
    evidence_id: str | None = None


class ValidatedReportSection(ContractModel):
    section_id: str
    heading: str = Field(min_length=1)
    claim_ids: tuple[str, ...]


class ValidatedReport(ContractModel):
    schema_version: Literal[VALIDATED_REPORT_VERSION] = VALIDATED_REPORT_VERSION
    report_id: str
    task_id: str
    brief_id: str
    plan_id: str
    run_id: str
    evidence_graph_sha256: str
    status: ReportStatus
    sections: tuple[ValidatedReportSection, ...]
    claims: tuple[Claim, ...]
    citations: tuple[Citation, ...]
    unresolved_gap_ids: tuple[str, ...] = ()
    unresolved_conflict_ids: tuple[str, ...] = ()
    disclosed_conflict_ids: tuple[str, ...] = ()
    author_review_required: Literal[True] = True
    publication_ready: Literal[False] = False


class ReportValidationResult(ContractModel):
    schema_version: Literal[VALIDATED_REPORT_VERSION] = VALIDATED_REPORT_VERSION
    status: ReportStatus
    report: ValidatedReport | None = None
    issues: tuple[ReportValidationIssue, ...] = ()
    deterministic_grounding_verified: bool = False
    semantic_correctness_verified: Literal[False] = False


class OfflineWriterResult(ContractModel):
    schema_version: Literal[WRITER_VERSION] = WRITER_VERSION
    run_id: str
    validation: ReportValidationResult
    events: tuple[RuntimeEventEnvelope, ...]
    ledger: BudgetLedger
    resumed: bool = False


@runtime_checkable
class Writer(Protocol):
    """Async-only producer of one untrusted candidate draft."""

    async def create_draft(
        self,
        *,
        task: ResearchTask,
        brief: ResearchBrief,
        plan: ValidatedResearchPlan,
        graph: EvidenceGraph,
        assessment: GapConflictAssessment,
    ) -> object: ...


class FakeWriter:
    """Scripted offline writer fixture; it never reads tools, Web, or a provider."""

    def __init__(self, response: object):
        self._response = response
        self.calls = 0

    async def create_draft(self, **_: object) -> object:
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _graph_hash(graph: EvidenceGraph) -> str:
    return sha256_hex(canonical_json_bytes(graph.model_dump(mode="json")))


def _issue(code: str, severity: Literal["blocking", "warning"], *, section_heading: str | None = None, claim_text: str | None = None, evidence_id: str | None = None) -> ReportValidationIssue:
    text_hash = sha256_hex(claim_text.encode("utf-8")) if claim_text else None
    identity = {"code": code, "severity": severity, "section_heading": section_heading, "claim_text_sha256": text_hash, "evidence_id": evidence_id}
    return ReportValidationIssue(issue_id=make_stable_id("validation", identity), code=code, severity=severity, section_heading=section_heading, claim_text_sha256=text_hash, evidence_id=evidence_id)


def _writer_validation_error_code(result: ReportValidationResult) -> str | None:
    if result.report is not None and result.report.claims:
        return None
    mapping = {"citation_evidence_unknown": "writer_evidence_reference_invalid", "citation_provenance_invalid": "writer_citation_invalid", "citation_quote_not_grounded": "writer_quote_invalid", "claim_without_valid_citation": "writer_claim_invalid", "required_section_missing": "writer_draft_empty"}
    for issue in result.issues:
        if issue.code in mapping:
            return mapping[issue.code]
    return None


def _validate_inputs(task: ResearchTask, brief: ResearchBrief, approval: BriefApproval, plan: ValidatedResearchPlan, graph: EvidenceGraph, assessment: GapConflictAssessment) -> None:
    require_approved_brief(task, brief, approval)
    if plan.task_id != task.task_id or plan.brief_id != brief.brief_id or plan.approval_id != approval.approval_id:
        raise WriterError("plan_not_executable", "writer requires the approved current plan")
    EvidenceGraph.model_validate(graph.model_dump(mode="json"))
    if graph.task_id != task.task_id or graph.plan_id != plan.plan_id or assessment.run_id != graph.run_id:
        raise WriterError("report_scope_invalid", "graph and assessment must bind to the current task, plan, and run")


def validate_report_draft(
    task: ResearchTask,
    brief: ResearchBrief,
    approval: BriefApproval,
    plan: ValidatedResearchPlan,
    graph: EvidenceGraph,
    assessment: GapConflictAssessment,
    draft: ReportDraft,
    *,
    outcome_unknown: bool = False,
) -> ReportValidationResult:
    """Accept only displayable Claim/Citation facts; semantic entailment remains human work."""

    _validate_inputs(task, brief, approval, plan, graph, assessment)
    if (draft.task_id, draft.brief_id, draft.plan_id, draft.run_id) != (task.task_id, brief.brief_id, plan.plan_id, graph.run_id):
        raise WriterError("writer_scope_invalid", "draft must bind exactly to the approved task, plan, and graph run")
    graph_hash = _graph_hash(graph)
    evidence = {item.evidence_id: item for item in graph.evidence_units}
    sources = {item.source_id: item for item in graph.sources}
    graph_edges = {(item.relation, item.from_id, item.to_id) for item in graph.edges}
    issues: list[ReportValidationIssue] = []
    claims: dict[str, Claim] = {}
    citations: dict[str, Citation] = {}
    section_claims: dict[str, set[str]] = {}

    for section in draft.sections:
        accepted: set[str] = set()
        for proposal in section.claims:
            valid_citations: list[Citation] = []
            for suggestion in proposal.citations:
                unit = evidence.get(suggestion.evidence_id)
                if unit is None:
                    issues.append(_issue("citation_evidence_unknown", "blocking", section_heading=section.heading, claim_text=proposal.text, evidence_id=suggestion.evidence_id))
                    continue
                if (
                    unit.source_id not in sources
                    or unit.locator.passage_id is None
                    or unit.locator.page_number is None
                    or ("source_contains_evidence", unit.source_id, unit.evidence_id) not in graph_edges
                    or not any(relation == "evidence_supports_subtask" and source == unit.evidence_id for relation, source, _ in graph_edges)
                ):
                    issues.append(_issue("citation_provenance_invalid", "blocking", section_heading=section.heading, claim_text=proposal.text, evidence_id=unit.evidence_id))
                    continue
                mapped = map_verbatim_span(suggestion.quote, unit.verbatim_content)
                if mapped.status != "ok" or mapped.start is None or mapped.end is None:
                    issues.append(_issue("citation_quote_not_grounded", "blocking", section_heading=section.heading, claim_text=proposal.text, evidence_id=unit.evidence_id))
                    continue
                claim = Claim.create(task.task_id, proposal.text, proposal.language, proposal.claim_type, tuple(proposal.entities))
                citation = Citation.create(claim.claim_id, unit.evidence_id, CitationRelation(suggestion.relation), mapped.evidence_text, mapped.start, mapped.end)
                valid_citations.append(citation)
            if not valid_citations:
                issues.append(_issue("claim_without_valid_citation", "blocking", section_heading=section.heading, claim_text=proposal.text))
                continue
            claim = Claim.create(task.task_id, proposal.text, proposal.language, proposal.claim_type, tuple(proposal.entities))
            claims[claim.claim_id] = claim
            for citation in valid_citations:
                citations[citation.citation_id] = citation
            accepted.add(claim.claim_id)
        if accepted:
            section_claims.setdefault(section.heading, set()).update(accepted)

    disclosed: set[str] = set()
    conflicts = {item.conflict_id: item for item in assessment.conflicts}
    for disclosure in draft.conflict_disclosures:
        conflict = conflicts.get(disclosure.conflict_id)
        if conflict is None or set(disclosure.evidence_ids) != set(conflict.evidence_ids):
            issues.append(_issue("conflict_disclosure_invalid", "blocking", evidence_id=disclosure.conflict_id))
        else:
            disclosed.add(disclosure.conflict_id)
    undisclosed = set(conflicts) - disclosed
    if undisclosed:
        issues.extend(_issue("unresolved_conflict_undisclosed", "blocking", evidence_id=item) for item in sorted(undisclosed))

    ordered_claims = tuple(sorted(claims.values(), key=lambda item: item.claim_id))
    ordered_citations = tuple(sorted(citations.values(), key=lambda item: item.citation_id))
    try:
        ContractBundle(task=task, brief=brief, brief_approvals=(approval,), subtasks=plan.subtasks, sources=tuple(sorted(sources.values(), key=lambda item: item.source_id)), evidence_units=tuple(sorted(evidence.values(), key=lambda item: item.evidence_id)), claims=ordered_claims, citations=ordered_citations)
    except ValueError as error:
        raise WriterError("report_contract_invalid", "program-generated report failed the shared Claim/Citation contract") from error

    sections = tuple(
        ValidatedReportSection(section_id=make_stable_id("section", {"plan_id": plan.plan_id, "heading": heading, "claim_ids": sorted(claim_ids)}), heading=heading, claim_ids=tuple(sorted(claim_ids)))
        for heading, claim_ids in sorted(section_claims.items())
    )
    if not sections and not draft.abstention_reason:
        issues.append(_issue("required_section_missing", "blocking"))
    if outcome_unknown:
        status = ReportStatus.manual_review_required
        issues.append(_issue("outcome_unknown", "blocking"))
    elif undisclosed:
        status = ReportStatus.manual_review_required
    elif not ordered_claims:
        status = ReportStatus.insufficient_evidence
    elif assessment.gaps or assessment.conflicts or issues:
        status = ReportStatus.partial
    else:
        status = ReportStatus.complete
    if draft.abstention_reason and not ordered_claims:
        sections = tuple(
            ValidatedReportSection(section_id=make_stable_id("section", {"plan_id": plan.plan_id, "heading": section.heading, "claim_ids": sorted(section_claims.get(section.heading, set()))}), heading=section.heading, claim_ids=tuple(sorted(section_claims.get(section.heading, set()))))
            for section in draft.sections
        )
    report = ValidatedReport(
        report_id=make_stable_id("report", {"task_id": task.task_id, "plan_id": plan.plan_id, "run_id": graph.run_id, "graph_sha256": graph_hash, "claim_ids": [item.claim_id for item in ordered_claims], "citation_ids": [item.citation_id for item in ordered_citations], "status": status.value}),
        task_id=task.task_id,
        brief_id=brief.brief_id,
        plan_id=plan.plan_id,
        run_id=graph.run_id,
        evidence_graph_sha256=graph_hash,
        status=status,
        sections=sections,
        claims=ordered_claims,
        citations=ordered_citations,
        unresolved_gap_ids=tuple(item.gap_id for item in assessment.gaps),
        unresolved_conflict_ids=tuple(sorted(conflicts)),
        disclosed_conflict_ids=tuple(sorted(disclosed)),
    )
    return ReportValidationResult(status=status, report=report, issues=tuple(sorted(set(issues), key=lambda item: item.issue_id)), deterministic_grounding_verified=bool(ordered_claims) and status is not ReportStatus.manual_review_required)


class SingleWriterRunner:
    """Controlled B07 entry: one fake writer call through the shared durable stream."""

    def __init__(self, writer: Writer, *, budget: BudgetSpec | None = None, token: CancellationToken | None = None, reservation_usage: TokenUsage | None = None) -> None:
        self._writer = writer
        self._budget = budget or BudgetSpec(max_provider_attempts=1, max_provider_calls=1, max_tool_attempts=64, max_tool_calls=64, max_retries=0, max_replans=1, run_timeout_s=45.0, operation_timeout_s=30.0)
        self._token = token or CancellationToken()
        self._reservation_usage = reservation_usage or TokenUsage()

    @staticmethod
    def _append(store: UnifiedEventStore, events: list[RuntimeEventEnvelope], event_type: RuntimeEventType, payload: dict[str, Any], *, operation_id: str | None = None, attempt_id: str | None = None, causal_parent_id: str | None = None) -> RuntimeEventEnvelope:
        event = create_runtime_event(store.run_id, len(events) + 1, event_type, payload=payload, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=causal_parent_id, previous_event_hash=events[-1].event_hash if events else GENESIS_HASH)
        store.append(event)
        events.append(event)
        return event

    def _lifecycle(self, store: UnifiedEventStore, events: list[RuntimeEventEnvelope], state: RunState, target: RunStatus, reason: str | None = None) -> RunState:
        next_state, event = transition(state, target, reason=reason)
        self._append(store, events, RuntimeEventType.lifecycle_transition, event.model_dump(mode="json"), causal_parent_id=events[-1].event_id if events else None)
        return next_state

    def _resume(self, initial: RunState, events: list[RuntimeEventEnvelope]) -> OfflineWriterResult | None:
        for event in reversed(events):
            if event.event_type is RuntimeEventType.operation_succeeded and event.payload.get("operation_name") == "single_writer":
                validation = ReportValidationResult.model_validate(event.payload["validation"])
                replayed = replay_runtime_events(initial, events, self._budget)
                return OfflineWriterResult(run_id=initial.run_id, validation=validation, events=tuple(events), ledger=replayed.ledger, resumed=True)
        replayed = replay_runtime_events(initial, events, self._budget)
        if replayed.manual_intervention is not None:
            validation = ReportValidationResult(status=ReportStatus.manual_review_required, issues=(_issue("outcome_unknown", "blocking"),))
            return OfflineWriterResult(run_id=initial.run_id, validation=validation, events=tuple(events), ledger=replayed.ledger, resumed=True)
        return None

    @staticmethod
    def _writer_error_code(code: str) -> str:
        return {"report_scope_invalid": "writer_scope_invalid", "report_contract_invalid": "writer_schema_invalid"}.get(code, code)

    @staticmethod
    def _validation_error_diagnostics(error: ValidationError) -> dict[str, object]:
        return writer_validation_error_diagnostics(error)

    async def run(
        self,
        task: ResearchTask,
        brief: ResearchBrief,
        approval: BriefApproval,
        plan: ValidatedResearchPlan,
        graph: EvidenceGraph,
        assessment: GapConflictAssessment,
        *,
        event_path: Path,
        checkpoint_path: Path,
        deadline_exceeded: bool = False,
        artifact_refs: dict[str, object] | None = None,
    ) -> OfflineWriterResult:
        _validate_inputs(task, brief, approval, plan, graph, assessment)
        initial = RunState(run_id=graph.run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True)
        store = UnifiedEventStore(event_path, run_id=graph.run_id)
        events = store.read_all()
        resumed = self._resume(initial, events)
        if resumed is not None:
            return resumed
        if self._token.cancelled or deadline_exceeded:
            code = "cancelled" if self._token.cancelled else "deadline_exceeded"
            validation = ReportValidationResult(status=ReportStatus.manual_review_required, issues=(_issue(code, "blocking"),))
            return OfflineWriterResult(run_id=graph.run_id, validation=validation, events=tuple(events), ledger=replay_runtime_events(initial, events, self._budget).ledger)
        state = reduce_runtime_events(initial, events, self._budget).run_state if events else initial
        if not events:
            self._append(store, events, RuntimeEventType.run_started, {"writer_version": WRITER_VERSION, "plan_id": plan.plan_id, "spec": self._budget.model_dump(mode="json")})
        if state.status is RunStatus.brief_pending:
            state = self._lifecycle(store, events, state, RunStatus.brief_approved)
        if state.status is RunStatus.brief_approved:
            state = self._lifecycle(store, events, state, RunStatus.researching)
        if state.status is not RunStatus.researching:
            raise WriterError("writer_not_admissible", "writer requires a nonterminal researching runtime state")
        operation_id = make_stable_id("operation", {"run_id": graph.run_id, "plan_id": plan.plan_id, "operation": "single_writer"})
        attempt_id = make_stable_id("attempt", {"operation_id": operation_id, "attempt_number": 1})
        usage = self._reservation_usage
        reserved = self._append(store, events, RuntimeEventType.operation_reserved, {"operation_kind": OperationKind.provider.value, "operation_name": "single_writer", "attempt_number": 1, "idempotent": False, "side_effecting": True, "usage": usage.model_dump(mode="json")}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=events[-1].event_id)
        try:
            reduce_runtime_events(initial, events, self._budget)
        except ValueError as error:
            raise WriterError("budget_exhausted", "writer reservation failed before durable dispatch") from error
        dispatched = self._append(store, events, RuntimeEventType.operation_dispatched, {"operation_kind": OperationKind.provider.value, "operation_name": "single_writer", "attempt_number": 1, "effective_timeout_s": self._budget.operation_timeout_s}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=reserved.event_id)
        writer_started = time.monotonic()
        try:
            raw = await asyncio.wait_for(self._writer.create_draft(task=task, brief=brief, plan=plan, graph=graph, assessment=assessment), timeout=self._budget.operation_timeout_s)
            usage = TokenUsage.model_validate(getattr(self._writer, "last_usage", usage).model_dump(mode="json") if isinstance(getattr(self._writer, "last_usage", usage), TokenUsage) else usage.model_dump(mode="json"))
            supplied_owned_fields = list(model_supplied_owned_fields(raw))
            draft = finalize_writer_content_draft(raw, task=task, brief=brief, plan=plan, graph=graph)
            validation = validate_report_draft(task, brief, approval, plan, graph, assessment, draft)
            writer_error_code = _writer_validation_error_code(validation)
            if writer_error_code is not None:
                proposal_claims = sum(len(section.claims) for section in draft.sections)
                proposal_citations = sum(len(claim.citations) for section in draft.sections for claim in section.claims)
                accepted_citations = len(validation.report.citations) if validation.report else 0
                raise WriterError(writer_error_code, "Writer draft has no displayable grounded Claim", {"failure_stage": "writer_validation", "contract_error_code": writer_error_code, "validation_issue_codes": sorted({issue.code for issue in validation.issues}), "sections_count": len(draft.sections), "claims_count": proposal_claims, "citations_count": proposal_citations, "evidence_total_count": len(graph.evidence_units), "evidence_valid_count": accepted_citations, "evidence_invalid_count": max(0, proposal_citations - accepted_citations), "normalization_input_count": proposal_claims, "normalization_accepted_count": len(validation.report.claims) if validation.report else 0, "rejected_item_count": max(0, proposal_claims - (len(validation.report.claims) if validation.report else 0))})
        except TimeoutError as error:
            self._append(store, events, RuntimeEventType.operation_unknown, {"operation_name": "single_writer", "error_code": "unknown_outcome", "attempt_number": 1, "usage": usage.model_dump(mode="json")}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
            self._append(store, events, RuntimeEventType.elapsed_recorded, {"elapsed_s": max(0.000001, time.monotonic() - writer_started)}, causal_parent_id=events[-1].event_id)
            validation = ReportValidationResult(status=ReportStatus.manual_review_required, issues=(_issue("outcome_unknown", "blocking"),))
            state = self._lifecycle(store, events, state, RunStatus.failed, "unknown_outcome")
            write_coordinated_checkpoint(checkpoint_path, CoordinatedCheckpointV2.from_result(replay_runtime_events(initial, events, self._budget)))
            return OfflineWriterResult(run_id=graph.run_id, validation=validation, events=tuple(events), ledger=replay_runtime_events(initial, events, self._budget).ledger)
        except WriterError as error:
            if error.code == "outcome_unknown":
                observed = getattr(self._writer, "last_usage", None)
                if isinstance(observed, TokenUsage):
                    usage = observed
                self._append(store, events, RuntimeEventType.operation_unknown, {"operation_name": "single_writer", "error_code": error.code, "attempt_number": 1, "usage": usage.model_dump(mode="json"), "diagnostics": error.diagnostics}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
                self._append(store, events, RuntimeEventType.elapsed_recorded, {"elapsed_s": max(0.000001, time.monotonic() - writer_started)}, causal_parent_id=events[-1].event_id)
                validation = ReportValidationResult(status=ReportStatus.manual_review_required, issues=(_issue("outcome_unknown", "blocking"),))
                state = self._lifecycle(store, events, state, RunStatus.failed, "unknown_outcome")
                replayed = replay_runtime_events(initial, events, self._budget)
                write_coordinated_checkpoint(checkpoint_path, CoordinatedCheckpointV2.from_result(replayed))
                return OfflineWriterResult(run_id=graph.run_id, validation=validation, events=tuple(events), ledger=replayed.ledger)
            code = self._writer_error_code(error.code)
            observed = getattr(self._writer, "last_usage", None)
            if isinstance(observed, TokenUsage):
                usage = observed
            diagnostics = error.diagnostics or {"failure_stage": "writer_application", "contract_error_code": code}
            self._append(store, events, RuntimeEventType.operation_failed, {"operation_name": "single_writer", "error_code": code, "attempt_number": 1, "usage": usage.model_dump(mode="json"), "diagnostics": diagnostics}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
            self._append(store, events, RuntimeEventType.elapsed_recorded, {"elapsed_s": max(0.000001, time.monotonic() - writer_started)}, causal_parent_id=events[-1].event_id)
            state = self._lifecycle(store, events, state, RunStatus.failed, code)
            write_coordinated_checkpoint(checkpoint_path, CoordinatedCheckpointV2.from_result(replay_runtime_events(initial, events, self._budget)))
            raise
        except (ValidationError, ValueError) as error:
            code = "writer_draft_invalid"
            diagnostics = self._validation_error_diagnostics(error) if isinstance(error, ValidationError) else {"failure_stage": "writer_application", "contract_error_code": "writer_schema_invalid"}
            self._append(store, events, RuntimeEventType.operation_failed, {"operation_name": "single_writer", "error_code": code, "attempt_number": 1, "usage": usage.model_dump(mode="json"), "diagnostics": diagnostics}, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
            self._append(store, events, RuntimeEventType.elapsed_recorded, {"elapsed_s": max(0.000001, time.monotonic() - writer_started)}, causal_parent_id=events[-1].event_id)
            state = self._lifecycle(store, events, state, RunStatus.failed, code)
            write_coordinated_checkpoint(checkpoint_path, CoordinatedCheckpointV2.from_result(replay_runtime_events(initial, events, self._budget)))
            raise WriterError(code, "untrusted writer draft failed before report display") from error
        result_hash = sha256_hex(canonical_json_bytes(validation.model_dump(mode="json")))
        success_payload = {"operation_name": "single_writer", "attempt_number": 1, "status": "success", "usage": usage.model_dump(mode="json"), "result_sha256": result_hash, "validation": validation.model_dump(mode="json"), "artifact_refs": artifact_refs or {}, "model_supplied_owned_fields": supplied_owned_fields}
        safe_draft = getattr(self._writer, "last_draft", None)
        if isinstance(safe_draft, dict):
            success_payload["draft"] = safe_draft
        self._append(store, events, RuntimeEventType.operation_succeeded, success_payload, operation_id=operation_id, attempt_id=attempt_id, causal_parent_id=dispatched.event_id)
        self._append(store, events, RuntimeEventType.elapsed_recorded, {"elapsed_s": max(0.000001, time.monotonic() - writer_started)}, causal_parent_id=events[-1].event_id)
        state = self._lifecycle(store, events, state, RunStatus.validating)
        state = self._lifecycle(store, events, state, RunStatus.insufficient_evidence if validation.status is ReportStatus.insufficient_evidence else RunStatus.complete)
        replayed = replay_runtime_events(initial, events, self._budget)
        write_coordinated_checkpoint(checkpoint_path, CoordinatedCheckpointV2.from_result(replayed))
        return OfflineWriterResult(run_id=graph.run_id, validation=validation, events=tuple(events), ledger=replayed.ledger)
