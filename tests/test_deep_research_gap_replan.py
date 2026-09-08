from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from litflow.deep_research.budgets import BudgetLedger, BudgetSpec
from litflow.deep_research.contracts import BriefApproval, BriefApprovalStatus, EvidenceLocator, EvidenceModality, EvidenceUnit, ResearchBrief, ResearchSubtask, ResearchTask, Source, SourceKind
from litflow.deep_research.executor import EvidenceGraph, EvidenceGraphEdge
from litflow.deep_research.gap_replan import (
    AssessmentContext,
    ConflictDraft,
    FakeGapConflictAssessor,
    GapConflictAssessmentDraft,
    ReplanOutcome,
    ReplanSubtaskDraft,
    SubtaskEvidenceRequirement,
    apply_bounded_replan,
    assess_evidence_graph,
    decide_replan,
)
from litflow.deep_research.planner import ValidatedResearchPlan
from litflow.deep_research.runtime_v2 import CoordinatedCheckpointV2, RuntimeEventType, UnifiedEventStore, create_runtime_event, reduce_runtime_events, replay_runtime_events
from litflow.deep_research.schema_export import write_gap_replan_schemas
from litflow.deep_research.state import RunState


NOW = datetime(2026, 9, 8, tzinfo=UTC)


def _fixture(with_evidence: bool = True):
    task = ResearchTask.create("Find support", "en", ("local-only",), "evidence", NOW)
    brief = ResearchBrief.create(task.task_id, "Find support", ("method",), ("web",), "evidence", ("one source",), ("local-only",), BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "human", NOW)
    subtask = ResearchSubtask.create(task.task_id, "Find evidence", "Required", expected_evidence=("method",), completion_criteria=("one",))
    plan = ValidatedResearchPlan(plan_id="dr-plan-" + "a" * 24, task_id=task.task_id, brief_id=brief.brief_id, approval_id=approval.approval_id, subtasks=(subtask,), topological_subtask_ids=(subtask.subtask_id,))
    run_id = "dr-run-" + "b" * 24
    source = Source.create(SourceKind.passage_corpus, "corpus:P1:" + "c" * 64, "Paper", "c" * 64, "en")
    units = ()
    edges = ()
    if with_evidence:
        unit = EvidenceUnit.create(source.source_id, EvidenceModality.text, EvidenceLocator(passage_id="P1:C1", page_number=1, span_start=0, span_end=7), "support", "en", {"evidence_type": "method"})
        units = (unit,)
        edges = (
            EvidenceGraphEdge(run_id=run_id, relation="subtask_retrieved_source", from_id=subtask.subtask_id, to_id=source.source_id),
            EvidenceGraphEdge(run_id=run_id, relation="source_contains_evidence", from_id=source.source_id, to_id=unit.evidence_id),
            EvidenceGraphEdge(run_id=run_id, relation="evidence_supports_subtask", from_id=unit.evidence_id, to_id=subtask.subtask_id),
        )
    graph = EvidenceGraph(run_id=run_id, task_id=task.task_id, plan_id=plan.plan_id, subtasks=(subtask,), sources=(source,), evidence_units=units, edges=tuple(sorted(edges, key=lambda item: (item.relation, item.from_id, item.to_id))))
    return task, brief, approval, plan, graph


def test_sufficient_graph_needs_no_replan_and_zero_assessor_calls():
    *_, graph = _fixture()
    assessor = FakeGapConflictAssessor(GapConflictAssessmentDraft(conflicts=()))
    assessment = asyncio.run(assess_evidence_graph(graph, (SubtaskEvidenceRequirement(subtask_id=graph.subtasks[0].subtask_id, required_evidence_types=("method",)),), AssessmentContext(completed_subtask_ids=(graph.subtasks[0].subtask_id,)), assessor))
    assert assessment.gaps == assessment.conflicts == ()
    assert assessor.calls == 1
    assert decide_replan(assessment, BudgetLedger(), BudgetSpec(max_replans=1)).outcome is ReplanOutcome.no_replan_needed


def test_zero_evidence_required_type_and_source_diversity_are_deterministic_gaps():
    *_, graph = _fixture(False)
    requirement = SubtaskEvidenceRequirement(subtask_id=graph.subtasks[0].subtask_id, min_evidence_count=1, required_evidence_types=("method",), min_source_count=2)
    assessment = asyncio.run(assess_evidence_graph(graph, (requirement,), AssessmentContext(completed_subtask_ids=(graph.subtasks[0].subtask_id,))))
    assert {gap.gap_type.value for gap in assessment.gaps} == {"subtask_no_evidence", "required_evidence_type_missing", "source_diversity_insufficient"}
    assert assessment == asyncio.run(assess_evidence_graph(graph, (requirement,), AssessmentContext(completed_subtask_ids=(graph.subtasks[0].subtask_id,))))


def test_conflict_draft_requires_two_existing_evidence_and_never_creates_evidence():
    task, brief, approval, plan, graph = _fixture()
    unit = graph.evidence_units[0]
    second = EvidenceUnit.create(graph.sources[0].source_id, EvidenceModality.text, EvidenceLocator(passage_id="P1:C2", page_number=2, span_start=0, span_end=8), "opposite", "en")
    graph = EvidenceGraph(run_id=graph.run_id, task_id=graph.task_id, plan_id=graph.plan_id, subtasks=graph.subtasks, sources=graph.sources, evidence_units=tuple(sorted((unit, second), key=lambda item: item.evidence_id)), edges=graph.edges)
    draft = GapConflictAssessmentDraft(conflicts=(ConflictDraft(local_key="c1", conflict_type="semantic_inconsistency", evidence_ids=(unit.evidence_id, second.evidence_id)),))
    result = asyncio.run(assess_evidence_graph(graph, (), AssessmentContext(completed_subtask_ids=(plan.subtasks[0].subtask_id,)), FakeGapConflictAssessor(draft)))
    assert len(result.conflicts) == 1 and result.conflicts[0].status == "unresolved"
    bad = FakeGapConflictAssessor(GapConflictAssessmentDraft(conflicts=(ConflictDraft(local_key="x", conflict_type="semantic_inconsistency", evidence_ids=(unit.evidence_id, "dr-evidence-" + "f" * 24)),)))
    with pytest.raises(ValueError, match="conflict_candidate_invalid"):
        asyncio.run(assess_evidence_graph(graph, (), AssessmentContext(), bad))


def test_replan_is_bounded_immutable_durable_and_idempotent(tmp_path: Path):
    task, brief, approval, plan, graph = _fixture(False)
    assessment = asyncio.run(assess_evidence_graph(graph, (SubtaskEvidenceRequirement(subtask_id=plan.subtasks[0].subtask_id),), AssessmentContext(completed_subtask_ids=(plan.subtasks[0].subtask_id,))))
    spec = BudgetSpec(max_replans=1)
    decision = decide_replan(assessment, BudgetLedger(), spec, original_plan_id=plan.plan_id)
    assert decision.outcome is ReplanOutcome.replan_allowed
    event_path = tmp_path / "events.jsonl"
    store = UnifiedEventStore(event_path, run_id=graph.run_id)
    store.append(create_runtime_event(graph.run_id, 1, RuntimeEventType.run_started, payload={"spec": spec.model_dump(mode="json")}, previous_event_hash="0" * 64))
    initial = RunState(run_id=graph.run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True)
    proposal = ReplanSubtaskDraft(question="Find missing method evidence", rationale="Closes verified gap", dependency_ids=(plan.subtasks[0].subtask_id,), expected_evidence=("method",), completion_criteria=("one",), locale="en", constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions)
    first = apply_bounded_replan(task, brief, approval, plan, assessment, decision, proposal, store, initial, spec)
    second = apply_bounded_replan(task, brief, approval, plan, assessment, decision, proposal, store, initial, spec)
    assert first == second and first.plan.parent_plan_id == plan.plan_id and plan.subtasks == (graph.subtasks[0],)
    assert sum(event.event_type is RuntimeEventType.replan_decided for event in store.read_all()) == 1
    replayed = replay_runtime_events(initial, store.read_all(), spec)
    assert replayed.ledger.replans == 1
    checkpoint = CoordinatedCheckpointV2.from_result(reduce_runtime_events(initial, store.read_all()[:1], spec))
    assert replay_runtime_events(initial, store.read_all(), spec, checkpoint=checkpoint) == replayed
    with pytest.raises(ValueError, match="replan_limit_exceeded"):
        decide_replan(assessment, replayed.ledger, spec, strict=True)


def test_replan_scope_dependency_cancel_deadline_and_unknown_fail_closed(tmp_path: Path):
    task, brief, approval, plan, graph = _fixture(False)
    assessment = asyncio.run(assess_evidence_graph(graph, (SubtaskEvidenceRequirement(subtask_id=plan.subtasks[0].subtask_id),), AssessmentContext()))
    spec = BudgetSpec(max_replans=1)
    assert decide_replan(assessment, BudgetLedger(), spec, cancelled=True).outcome is ReplanOutcome.cancelled
    assert decide_replan(assessment, BudgetLedger(), spec, deadline_exceeded=True).outcome is ReplanOutcome.deadline_exceeded
    assert decide_replan(assessment, BudgetLedger(), spec, outcome_unknown=True).outcome is ReplanOutcome.manual_intervention_required
    invalid = ReplanSubtaskDraft(question="x", rationale="x", locale="en", constraints=("web",), scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions)
    store = UnifiedEventStore(tmp_path / "events.jsonl", run_id=graph.run_id)
    with pytest.raises(ValueError, match="replan_scope_violation"):
        apply_bounded_replan(task, brief, approval, plan, assessment, decide_replan(assessment, BudgetLedger(), spec, original_plan_id=plan.plan_id), invalid, store, RunState(run_id=graph.run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True), spec)


def test_gap_replan_schemas_are_byte_stable(tmp_path: Path):
    written = write_gap_replan_schemas(tmp_path)
    committed = Path("docs/deep_research/gap_replan/v1")
    for name, path in written.items():
        assert path.read_bytes() == (committed / name).read_bytes()
