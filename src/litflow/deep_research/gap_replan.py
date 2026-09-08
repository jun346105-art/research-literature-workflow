"""Deterministic evidence-gap assessment and one bounded immutable replan."""
from __future__ import annotations

from enum import Enum
from typing import Literal, Protocol

from pydantic import Field, field_validator, model_validator

from .budgets import BudgetLedger, BudgetSpec
from .contracts import BriefApproval, ContractBundle, ContractModel, ResearchBrief, ResearchSubtask, ResearchTask
from .executor import EvidenceGraph
from .identity import make_stable_id
from .planner import ValidatedResearchPlan, require_approved_brief
from .runtime_v2 import RuntimeEventEnvelope, RuntimeEventType, UnifiedEventStore, create_runtime_event, replay_runtime_events
from .state import RunState


GAP_REPLAN_VERSION = "dr-gap-replan-v1"


class GapType(str, Enum):
    subtask_no_evidence = "subtask_no_evidence"
    evidence_count_below_required = "evidence_count_below_required"
    required_evidence_type_missing = "required_evidence_type_missing"
    source_diversity_insufficient = "source_diversity_insufficient"
    dependency_unsatisfied = "dependency_unsatisfied"
    scope_not_covered = "scope_not_covered"


class ConflictType(str, Enum):
    semantic_inconsistency = "semantic_inconsistency"
    structured_value_conflict = "structured_value_conflict"
    provenance_identity_conflict = "provenance_identity_conflict"


class ReplanOutcome(str, Enum):
    no_replan_needed = "no_replan_needed"
    replan_allowed = "replan_allowed"
    insufficient_evidence = "insufficient_evidence"
    budget_exhausted = "budget_exhausted"
    deadline_exceeded = "deadline_exceeded"
    manual_intervention_required = "manual_intervention_required"
    cancelled = "cancelled"


class SubtaskEvidenceRequirement(ContractModel):
    subtask_id: str
    min_evidence_count: int = Field(default=1, ge=0)
    required_evidence_types: tuple[str, ...] = ()
    min_source_count: int = Field(default=1, ge=0)
    required_scope_labels: tuple[str, ...] = ()


class AssessmentContext(ContractModel):
    completed_subtask_ids: tuple[str, ...] = ()
    covered_scope_labels: tuple[str, ...] = ()


class EvidenceGap(ContractModel):
    schema_version: Literal[GAP_REPLAN_VERSION] = GAP_REPLAN_VERSION
    gap_id: str
    run_id: str
    subtask_id: str
    gap_type: GapType
    observed: tuple[str, ...] = ()
    required: tuple[str, ...] = ()


class ConflictDraft(ContractModel):
    local_key: str = Field(min_length=1)
    conflict_type: ConflictType
    evidence_ids: tuple[str, ...]

    @field_validator("evidence_ids")
    @classmethod
    def require_distinct_pair(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) < 2 or len(value) != len(set(value)):
            raise ValueError("potential conflict requires at least two distinct evidence IDs")
        return value


class GapConflictAssessmentDraft(ContractModel):
    schema_version: Literal["dr-gap-conflict-draft-v1"] = "dr-gap-conflict-draft-v1"
    conflicts: tuple[ConflictDraft, ...] = ()


class PotentialConflict(ContractModel):
    schema_version: Literal[GAP_REPLAN_VERSION] = GAP_REPLAN_VERSION
    conflict_id: str
    run_id: str
    conflict_type: ConflictType
    evidence_ids: tuple[str, ...]
    status: Literal["unresolved"] = "unresolved"


class GapConflictAssessment(ContractModel):
    schema_version: Literal[GAP_REPLAN_VERSION] = GAP_REPLAN_VERSION
    assessment_id: str
    run_id: str
    gaps: tuple[EvidenceGap, ...] = ()
    conflicts: tuple[PotentialConflict, ...] = ()


class GapConflictAssessor(Protocol):
    async def assess(self, graph: EvidenceGraph) -> object: ...


class FakeGapConflictAssessor:
    def __init__(self, draft: object):
        self.draft = draft
        self.calls = 0

    async def assess(self, graph: EvidenceGraph) -> object:
        self.calls += 1
        return self.draft


class ReplanDecisionRecord(ContractModel):
    schema_version: Literal[GAP_REPLAN_VERSION] = GAP_REPLAN_VERSION
    decision_id: str
    run_id: str
    assessment_id: str
    original_plan_id: str
    outcome: ReplanOutcome
    replan_ordinal: int = Field(default=0, ge=0)
    gap_ids: tuple[str, ...] = ()
    conflict_ids: tuple[str, ...] = ()


class ReplanSubtaskDraft(ContractModel):
    question: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    dependency_ids: tuple[str, ...] = ()
    expected_evidence: tuple[str, ...] = ()
    completion_criteria: tuple[str, ...] = ()
    locale: str
    constraints: tuple[str, ...] = ()
    scope_inclusions: tuple[str, ...] = ()
    scope_exclusions: tuple[str, ...] = ()


class ReplannedResearchPlan(ContractModel):
    schema_version: Literal["dr-replanned-research-plan-v1"] = "dr-replanned-research-plan-v1"
    plan_id: str
    parent_plan_id: str
    decision_id: str
    task_id: str
    brief_id: str
    approval_id: str
    subtasks: tuple[ResearchSubtask, ...]
    topological_subtask_ids: tuple[str, ...]


class BoundedReplanResult(ContractModel):
    decision: ReplanDecisionRecord
    plan: ReplannedResearchPlan
    events: tuple[RuntimeEventEnvelope, ...]
    ledger: BudgetLedger


def _gap(run_id: str, subtask_id: str, gap_type: GapType, observed: tuple[str, ...], required: tuple[str, ...]) -> EvidenceGap:
    payload = {"run_id": run_id, "subtask_id": subtask_id, "gap_type": gap_type.value, "observed": list(observed), "required": list(required)}
    return EvidenceGap(gap_id=make_stable_id("gap", payload), run_id=run_id, subtask_id=subtask_id, gap_type=gap_type, observed=observed, required=required)


async def assess_evidence_graph(graph: EvidenceGraph, requirements: tuple[SubtaskEvidenceRequirement, ...], context: AssessmentContext, assessor: GapConflictAssessor | None = None) -> GapConflictAssessment:
    graph = EvidenceGraph.model_validate(graph.model_dump(mode="json"))
    subtask_ids = {item.subtask_id for item in graph.subtasks}
    evidence_by_id = {item.evidence_id: item for item in graph.evidence_units}
    evidence_to_subtask = {edge.from_id: edge.to_id for edge in graph.edges if edge.relation == "evidence_supports_subtask"}
    source_for_evidence = {edge.to_id: edge.from_id for edge in graph.edges if edge.relation == "source_contains_evidence"}
    requirement_by_id = {item.subtask_id: item for item in requirements}
    if len(requirement_by_id) != len(requirements) or set(requirement_by_id) - subtask_ids:
        raise ValueError("evidence_reference_invalid: requirement references unknown subtask")
    gaps: list[EvidenceGap] = []
    for subtask in graph.subtasks:
        requirement = requirement_by_id.get(subtask.subtask_id, SubtaskEvidenceRequirement(subtask_id=subtask.subtask_id))
        ids = sorted(evidence_id for evidence_id, owner in evidence_to_subtask.items() if owner == subtask.subtask_id)
        types = sorted({evidence_by_id[item].provenance_metadata.get("evidence_type", "") for item in ids} - {""})
        sources = sorted({source_for_evidence[item] for item in ids if item in source_for_evidence})
        if not ids:
            gaps.append(_gap(graph.run_id, subtask.subtask_id, GapType.subtask_no_evidence, (), ("evidence",)))
        elif len(ids) < requirement.min_evidence_count:
            gaps.append(_gap(graph.run_id, subtask.subtask_id, GapType.evidence_count_below_required, (str(len(ids)),), (str(requirement.min_evidence_count),)))
        missing_types = tuple(sorted(set(requirement.required_evidence_types) - set(types)))
        if missing_types:
            gaps.append(_gap(graph.run_id, subtask.subtask_id, GapType.required_evidence_type_missing, tuple(types), missing_types))
        if len(sources) < requirement.min_source_count:
            gaps.append(_gap(graph.run_id, subtask.subtask_id, GapType.source_diversity_insufficient, tuple(sources), (str(requirement.min_source_count),)))
        missing_dependencies = tuple(sorted(set(subtask.dependency_ids) - set(context.completed_subtask_ids)))
        if missing_dependencies:
            gaps.append(_gap(graph.run_id, subtask.subtask_id, GapType.dependency_unsatisfied, (), missing_dependencies))
        missing_scope = tuple(sorted(set(requirement.required_scope_labels) - set(context.covered_scope_labels)))
        if missing_scope:
            gaps.append(_gap(graph.run_id, subtask.subtask_id, GapType.scope_not_covered, tuple(sorted(context.covered_scope_labels)), missing_scope))
    conflicts: list[PotentialConflict] = []
    if assessor is not None:
        draft = GapConflictAssessmentDraft.model_validate(await assessor.assess(graph))
        known_evidence = set(evidence_by_id)
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for item in draft.conflicts:
            ids = tuple(sorted(item.evidence_ids))
            if not set(ids).issubset(known_evidence):
                raise ValueError("conflict_candidate_invalid: evidence reference is unknown")
            identity = (item.conflict_type.value, ids)
            if identity in seen:
                continue
            seen.add(identity)
            payload = {"run_id": graph.run_id, "conflict_type": item.conflict_type.value, "evidence_ids": list(ids)}
            conflicts.append(PotentialConflict(conflict_id=make_stable_id("conflict", payload), run_id=graph.run_id, conflict_type=item.conflict_type, evidence_ids=ids))
    gaps_tuple = tuple(sorted(set(gaps), key=lambda item: item.gap_id))
    conflicts_tuple = tuple(sorted(conflicts, key=lambda item: item.conflict_id))
    identity = {"run_id": graph.run_id, "gap_ids": [item.gap_id for item in gaps_tuple], "conflict_ids": [item.conflict_id for item in conflicts_tuple]}
    return GapConflictAssessment(assessment_id=make_stable_id("assessment", identity), run_id=graph.run_id, gaps=gaps_tuple, conflicts=conflicts_tuple)


def decide_replan(assessment: GapConflictAssessment, ledger: BudgetLedger, spec: BudgetSpec, *, original_plan_id: str = "dr-plan-" + "0" * 24, cancelled: bool = False, deadline_exceeded: bool = False, outcome_unknown: bool = False, strict: bool = False) -> ReplanDecisionRecord:
    if cancelled:
        outcome = ReplanOutcome.cancelled
    elif outcome_unknown:
        outcome = ReplanOutcome.manual_intervention_required
    elif deadline_exceeded:
        outcome = ReplanOutcome.deadline_exceeded
    elif not assessment.gaps and not assessment.conflicts:
        outcome = ReplanOutcome.no_replan_needed
    elif ledger.replans >= spec.max_replans:
        if strict:
            raise ValueError("replan_limit_exceeded")
        outcome = ReplanOutcome.budget_exhausted
    else:
        outcome = ReplanOutcome.replan_allowed
    identity = {"run_id": assessment.run_id, "assessment_id": assessment.assessment_id, "original_plan_id": original_plan_id, "outcome": outcome.value, "ordinal": ledger.replans}
    return ReplanDecisionRecord(decision_id=make_stable_id("replan", identity), run_id=assessment.run_id, assessment_id=assessment.assessment_id, original_plan_id=original_plan_id, outcome=outcome, replan_ordinal=ledger.replans, gap_ids=tuple(item.gap_id for item in assessment.gaps), conflict_ids=tuple(item.conflict_id for item in assessment.conflicts))


def apply_bounded_replan(task: ResearchTask, brief: ResearchBrief, approval: BriefApproval, original: ValidatedResearchPlan, assessment: GapConflictAssessment, decision: ReplanDecisionRecord, proposal: ReplanSubtaskDraft, store: UnifiedEventStore, initial_state: RunState, spec: BudgetSpec) -> BoundedReplanResult:
    require_approved_brief(task, brief, approval)
    if decision.outcome is not ReplanOutcome.replan_allowed or decision.run_id != store.run_id or assessment.run_id != store.run_id or decision.assessment_id != assessment.assessment_id or decision.original_plan_id != original.plan_id:
        raise ValueError("replan_not_admissible")
    if proposal.locale != task.locale or proposal.constraints != brief.constraints or proposal.scope_inclusions != brief.scope_inclusions or proposal.scope_exclusions != brief.scope_exclusions:
        raise ValueError("replan_scope_violation")
    existing_ids = {item.subtask_id for item in original.subtasks}
    if not set(proposal.dependency_ids).issubset(existing_ids):
        raise ValueError("replan_dependency_invalid")
    semantic = (proposal.question, proposal.rationale, proposal.expected_evidence, proposal.completion_criteria)
    if any((item.question, item.rationale, item.expected_evidence, item.completion_criteria) == semantic for item in original.subtasks):
        raise ValueError("replan_not_admissible: equivalent subtask already exists")
    added = ResearchSubtask.create(task.task_id, proposal.question, proposal.rationale, proposal.dependency_ids, proposal.expected_evidence, proposal.completion_criteria)
    bundle = ContractBundle(task=task, brief=brief, brief_approvals=(approval,), subtasks=original.subtasks + (added,))
    topo = bundle.topological_subtask_ids()
    by_id = {item.subtask_id: item for item in bundle.subtasks}
    subtasks = tuple(by_id[item] for item in topo)
    plan_identity = {"parent_plan_id": original.plan_id, "decision_id": decision.decision_id, "subtask_ids": list(topo)}
    plan = ReplannedResearchPlan(plan_id=make_stable_id("plan", plan_identity), parent_plan_id=original.plan_id, decision_id=decision.decision_id, task_id=task.task_id, brief_id=brief.brief_id, approval_id=approval.approval_id, subtasks=subtasks, topological_subtask_ids=topo)
    events = store.read_all()
    existing = next((event for event in events if event.event_type is RuntimeEventType.replan_decided and event.payload.get("decision_id") == decision.decision_id), None)
    if existing is None:
        replayed = replay_runtime_events(initial_state, events, spec)
        if replayed.manual_intervention is not None or any(record.status.value == "outcome_unknown" for record in replayed.journal.records):
            raise ValueError("replan_not_admissible: outcome_unknown")
        if replayed.ledger.replans >= spec.max_replans:
            raise ValueError("replan_limit_exceeded")
        event = create_runtime_event(store.run_id, len(events) + 1, RuntimeEventType.replan_decided, payload={"decision_id": decision.decision_id, "admitted": True, "old_plan_id": original.plan_id, "proposed_plan_id": plan.plan_id, "replan_ordinal": replayed.ledger.replans}, causal_parent_id=events[-1].event_id if events else None, previous_event_hash=events[-1].event_hash if events else "0" * 64)
        store.append(event)
        events.append(event)
    replayed = replay_runtime_events(initial_state, events, spec)
    return BoundedReplanResult(decision=decision, plan=plan, events=tuple(events), ledger=replayed.ledger)
