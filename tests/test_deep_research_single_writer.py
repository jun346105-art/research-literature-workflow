from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from litflow.deep_research.budgets import BudgetLedger, BudgetSpec
from litflow.deep_research.contracts import BriefApproval, BriefApprovalStatus, EvidenceLocator, EvidenceModality, EvidenceUnit, ResearchBrief, ResearchTask, Source, SourceKind
from litflow.deep_research.executor import EvidenceGraph, EvidenceGraphEdge, LocalResearchExecutor, ReadOnlyToolRegistry
from litflow.deep_research.gap_replan import AssessmentContext, ConflictType, GapConflictAssessment, PotentialConflict, ReplanSubtaskDraft, SubtaskEvidenceRequirement, apply_bounded_replan, assess_evidence_graph, decide_replan
from litflow.deep_research.identity import canonical_json_bytes, make_stable_id, sha256_hex
from litflow.deep_research.planner import FakePlanner, PlannerDraft, PlannerSubtaskDraft, plan_approved_brief
from litflow.deep_research.policies import CancellationToken
from litflow.deep_research.runtime_v2 import CoordinatedCheckpointV2, RuntimeEventType, UnifiedEventStore, create_runtime_event, reduce_runtime_events, replay_runtime_events
from litflow.deep_research.schema_export import render_writer_schemas, write_writer_schemas
from litflow.deep_research.state import RunState
from litflow.deep_research.writer import FakeWriter, ReportDraft, ReportStatus, SingleWriterRunner, WriterError, validate_report_draft


NOW = datetime(2026, 9, 8, tzinfo=UTC)


def _corpus():
    text = "Alpha evidence is preserved in this local passage."
    return [{"passage_id": "P1:P1_chunk_0001", "paper_key": "P1", "citation_key": "cite", "title": "Paper", "chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "source_context_sha256": "a" * 64}]


def _inputs(tmp_path: Path, *, evidence: bool = True):
    task = ResearchTask.create("Which local evidence supports alpha?", "en", ("local-only",), "grounded_report", NOW)
    brief = ResearchBrief.create(task.task_id, "Find local alpha evidence.", ("alpha",), (), "report", ("quote",), ("local-only",), BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "human", NOW)
    draft = PlannerDraft(task_id=task.task_id, brief_id=brief.brief_id, locale="en", constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions, subtasks=(PlannerSubtaskDraft(local_key="find", question="alpha evidence", rationale="find", expected_evidence=("quote",), completion_criteria=("one",)),))
    plan = asyncio.run(plan_approved_brief(task, brief, approval, FakePlanner(draft)))
    if evidence:
        executor = LocalResearchExecutor(ReadOnlyToolRegistry(_corpus()))
        executed = asyncio.run(executor.execute(task, brief, approval, plan, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "executor.checkpoint.json"))
        graph = executed.evidence_graph
    else:
        run_id = make_stable_id("run", {"test": "writer-empty", "plan_id": plan.plan_id})
        graph = EvidenceGraph(run_id=run_id, task_id=task.task_id, plan_id=plan.plan_id, subtasks=tuple(sorted(plan.subtasks, key=lambda item: item.subtask_id)), sources=(), evidence_units=(), edges=())
    assessment = asyncio.run(assess_evidence_graph(graph, (), AssessmentContext(completed_subtask_ids=tuple(item.subtask_id for item in plan.subtasks))))
    return task, brief, approval, plan, graph, assessment


def _draft(task, brief, plan, graph, *, claims, disclosures=(), extra=False):
    value = {"schema_version": "dr-report-draft-v1", "task_id": task.task_id, "brief_id": brief.brief_id, "plan_id": plan.plan_id, "run_id": graph.run_id, "sections": [{"heading": "Findings", "claims": claims}], "conflict_disclosures": list(disclosures)}
    if extra:
        value["presentation_hint"] = "harmless"
    return value


def _claim(evidence_id: str, quote: str, *, text: str = "Alpha is supported."):
    return {"text": text, "language": "en", "citations": [{"evidence_id": evidence_id, "quote": quote, "relation": "support"}]}


def test_b04_to_b07_offline_e2e_complete_durable_resume_and_replay(tmp_path: Path):
    task, brief, approval, plan, graph, assessment = _inputs(tmp_path)
    unit = graph.evidence_units[0]
    before = sha256_hex(canonical_json_bytes(graph.model_dump(mode="json")))
    writer = FakeWriter(_draft(task, brief, plan, graph, claims=[_claim(unit.evidence_id, unit.verbatim_content), _claim(unit.evidence_id, unit.verbatim_content)] , extra=True))
    runner = SingleWriterRunner(writer)
    result = asyncio.run(runner.run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "writer.checkpoint.json"))
    assert result.validation.status is ReportStatus.complete
    assert result.validation.report is not None
    assert len(result.validation.report.claims) == len(result.validation.report.citations) == 1
    assert result.validation.report.author_review_required and not result.validation.report.publication_ready
    assert sha256_hex(canonical_json_bytes(graph.model_dump(mode="json"))) == before
    types = [event.event_type for event in result.events]
    assert types.index(RuntimeEventType.operation_reserved) < types.index(RuntimeEventType.operation_dispatched) < types.index(RuntimeEventType.operation_succeeded)
    resumed_writer = FakeWriter(AssertionError("resume must not call writer"))
    resumed = asyncio.run(SingleWriterRunner(resumed_writer).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "writer.checkpoint.json"))
    assert resumed.resumed and resumed.validation == result.validation and resumed_writer.calls == 0
    initial = RunState(run_id=graph.run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True)
    full = replay_runtime_events(initial, list(result.events), runner._budget)
    checkpoint = CoordinatedCheckpointV2.from_result(reduce_runtime_events(initial, list(result.events)[:4], runner._budget))
    assert replay_runtime_events(initial, list(result.events), runner._budget, checkpoint=checkpoint) == full
    assert writer.calls == 1


def test_partial_dedupes_claims_and_rejects_fake_cross_run_and_bad_quotes(tmp_path: Path):
    task, brief, approval, plan, graph, assessment = _inputs(tmp_path)
    unit = graph.evidence_units[0]
    raw = _draft(task, brief, plan, graph, claims=[_claim(unit.evidence_id, unit.verbatim_content), _claim(unit.evidence_id, unit.verbatim_content), _claim("dr-evidence-" + "f" * 24, "invented", text="Fake evidence."), _claim(unit.evidence_id, "not in evidence", text="Bad quote.")])
    result = validate_report_draft(task, brief, approval, plan, graph, assessment, ReportDraft.model_validate(raw))
    assert result.status is ReportStatus.partial
    assert result.report is not None and len(result.report.claims) == len(result.report.citations) == 1
    assert {issue.code for issue in result.issues} >= {"citation_evidence_unknown", "citation_quote_not_grounded", "claim_without_valid_citation"}


def test_empty_evidence_missing_fields_and_graph_mutation_fail_closed(tmp_path: Path):
    task, brief, approval, plan, graph, assessment = _inputs(tmp_path, evidence=False)
    raw = _draft(task, brief, plan, graph, claims=[{"text": "Unsupported", "language": "en", "citations": []}])
    result = validate_report_draft(task, brief, approval, plan, graph, assessment, ReportDraft.model_validate(raw))
    assert result.status is ReportStatus.insufficient_evidence and result.report is not None
    with pytest.raises(ValidationError):
        ReportDraft.model_validate({"schema_version": "dr-report-draft-v1"})
    with pytest.raises(ValidationError, match="program-controlled"):
        ReportDraft.model_validate({**raw, "evidence_graph": graph.model_dump(mode="json")})
    with pytest.raises(WriterError, match="writer_draft_invalid"):
        asyncio.run(SingleWriterRunner(FakeWriter({"schema_version": "dr-report-draft-v1"})).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "malformed.jsonl", checkpoint_path=tmp_path / "malformed.checkpoint.json"))


def test_missing_graph_provenance_edge_rejects_an_otherwise_known_evidence(tmp_path: Path):
    task, brief, approval, plan, graph, assessment = _inputs(tmp_path)
    unit = graph.evidence_units[0]
    graph = EvidenceGraph(run_id=graph.run_id, task_id=graph.task_id, plan_id=graph.plan_id, subtasks=graph.subtasks, sources=graph.sources, evidence_units=graph.evidence_units, edges=tuple(item for item in graph.edges if item.relation != "source_contains_evidence"))
    result = validate_report_draft(task, brief, approval, plan, graph, assessment, ReportDraft.model_validate(_draft(task, brief, plan, graph, claims=[_claim(unit.evidence_id, unit.verbatim_content)])))
    assert result.status is ReportStatus.insufficient_evidence
    assert {issue.code for issue in result.issues} >= {"citation_provenance_invalid", "claim_without_valid_citation"}


def test_unresolved_conflict_requires_exact_two_sided_disclosure(tmp_path: Path):
    task, brief, approval, plan, graph, assessment = _inputs(tmp_path)
    first = graph.evidence_units[0]
    second = EvidenceUnit.create(graph.sources[0].source_id, EvidenceModality.text, EvidenceLocator(passage_id="P1:P1_chunk_0002", page_number=2, span_start=0, span_end=8), "Opposite", "en")
    graph = EvidenceGraph(run_id=graph.run_id, task_id=graph.task_id, plan_id=graph.plan_id, subtasks=graph.subtasks, sources=graph.sources, evidence_units=tuple(sorted((first, second), key=lambda item: item.evidence_id)), edges=graph.edges)
    conflict = PotentialConflict(conflict_id=make_stable_id("conflict", {"run_id": graph.run_id, "pair": sorted((first.evidence_id, second.evidence_id))}), run_id=graph.run_id, conflict_type=ConflictType.semantic_inconsistency, evidence_ids=tuple(sorted((first.evidence_id, second.evidence_id))))
    assessment = GapConflictAssessment(assessment_id=make_stable_id("assessment", {"run_id": graph.run_id, "conflict": conflict.conflict_id}), run_id=graph.run_id, conflicts=(conflict,))
    claims = [_claim(first.evidence_id, first.verbatim_content)]
    undisclosed = validate_report_draft(task, brief, approval, plan, graph, assessment, ReportDraft.model_validate(_draft(task, brief, plan, graph, claims=claims)))
    assert undisclosed.status is ReportStatus.manual_review_required
    disclosed = validate_report_draft(task, brief, approval, plan, graph, assessment, ReportDraft.model_validate(_draft(task, brief, plan, graph, claims=claims, disclosures=({"conflict_id": conflict.conflict_id, "evidence_ids": list(conflict.evidence_ids), "label": "disputed"},))))
    assert disclosed.status is ReportStatus.partial


def test_cancel_deadline_budget_unknown_and_fsync_failure_never_call_writer(tmp_path: Path, monkeypatch):
    task, brief, approval, plan, graph, assessment = _inputs(tmp_path)
    token = CancellationToken(); token.request()
    cancelled_writer = FakeWriter({})
    cancelled = asyncio.run(SingleWriterRunner(cancelled_writer, token=token).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "cancelled.jsonl", checkpoint_path=tmp_path / "cancelled.checkpoint.json"))
    assert cancelled.validation.status is ReportStatus.manual_review_required and cancelled_writer.calls == 0
    deadline_writer = FakeWriter({})
    deadline = asyncio.run(SingleWriterRunner(deadline_writer).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "deadline.jsonl", checkpoint_path=tmp_path / "deadline.checkpoint.json", deadline_exceeded=True))
    assert deadline.validation.status is ReportStatus.manual_review_required and deadline_writer.calls == 0
    budget_writer = FakeWriter({})
    with pytest.raises(WriterError, match="budget_exhausted"):
        asyncio.run(SingleWriterRunner(budget_writer, budget=BudgetSpec(max_provider_calls=0, max_retries=0, max_replans=1)).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "budget.jsonl", checkpoint_path=tmp_path / "budget.checkpoint.json"))
    assert budget_writer.calls == 0
    unknown_writer = FakeWriter(TimeoutError())
    unknown = asyncio.run(SingleWriterRunner(unknown_writer).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "unknown.jsonl", checkpoint_path=tmp_path / "unknown.checkpoint.json"))
    assert unknown.validation.status is ReportStatus.manual_review_required and unknown.validation.report is None
    fsync_writer = FakeWriter({})
    monkeypatch.setattr("litflow.deep_research.runtime_v2.os.fsync", lambda _: (_ for _ in ()).throw(OSError("fsync")))
    with pytest.raises(OSError, match="fsync"):
        asyncio.run(SingleWriterRunner(fsync_writer).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "fsync.jsonl", checkpoint_path=tmp_path / "fsync.checkpoint.json"))
    assert fsync_writer.calls == 0


def test_terminal_event_before_checkpoint_resumes_without_new_writer_call(tmp_path: Path, monkeypatch):
    task, brief, approval, plan, graph, assessment = _inputs(tmp_path)
    unit = graph.evidence_units[0]
    writer = FakeWriter(_draft(task, brief, plan, graph, claims=[_claim(unit.evidence_id, unit.verbatim_content)]))
    monkeypatch.setattr("litflow.deep_research.writer.write_coordinated_checkpoint", lambda *_: (_ for _ in ()).throw(OSError("checkpoint")))
    with pytest.raises(OSError, match="checkpoint"):
        asyncio.run(SingleWriterRunner(writer).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "writer.checkpoint.json"))
    assert writer.calls == 1
    resumed_writer = FakeWriter(AssertionError("must not retry"))
    resumed = asyncio.run(SingleWriterRunner(resumed_writer).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "writer.checkpoint.json"))
    assert resumed.resumed and resumed_writer.calls == 0


def test_one_bounded_replan_then_new_graph_can_be_written_but_second_is_blocked(tmp_path: Path):
    task, brief, approval, plan, empty_graph, empty_assessment = _inputs(tmp_path, evidence=False)
    spec = BudgetSpec(max_provider_calls=1, max_tool_calls=64, max_retries=0, max_replans=1, run_timeout_s=45, operation_timeout_s=30)
    decision = decide_replan(empty_assessment, BudgetLedger(), spec, original_plan_id=plan.plan_id)
    store = UnifiedEventStore(tmp_path / "replan.jsonl", run_id=empty_graph.run_id)
    store.append(create_runtime_event(empty_graph.run_id, 1, RuntimeEventType.run_started, payload={"spec": spec.model_dump(mode="json")}, previous_event_hash="0" * 64))
    proposal = ReplanSubtaskDraft(question="Find alpha evidence", rationale="fills gap", dependency_ids=(plan.subtasks[0].subtask_id,), expected_evidence=("quote",), completion_criteria=("one",), locale=task.locale, constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions)
    replanned = apply_bounded_replan(task, brief, approval, plan, empty_assessment, decision, proposal, store, RunState(run_id=empty_graph.run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True), spec)
    source = Source.create(SourceKind.passage_corpus, "corpus:P2:" + "b" * 64, "Paper", "b" * 64, "en")
    original_unit = EvidenceUnit.create(source.source_id, EvidenceModality.text, EvidenceLocator(passage_id="P2:C0", page_number=1, span_start=0, span_end=17), "original evidence", "en")
    unit = EvidenceUnit.create(source.source_id, EvidenceModality.text, EvidenceLocator(passage_id="P2:C1", page_number=2, span_start=0, span_end=14), "alpha evidence", "en")
    original_subtask, added_subtask = replanned.plan.subtasks
    graph = EvidenceGraph(run_id=empty_graph.run_id, task_id=task.task_id, plan_id=replanned.plan.plan_id, subtasks=tuple(sorted(replanned.plan.subtasks, key=lambda item: item.subtask_id)), sources=(source,), evidence_units=tuple(sorted((original_unit, unit), key=lambda item: item.evidence_id)), edges=tuple(sorted((EvidenceGraphEdge(run_id=empty_graph.run_id, relation="subtask_retrieved_source", from_id=original_subtask.subtask_id, to_id=source.source_id), EvidenceGraphEdge(run_id=empty_graph.run_id, relation="subtask_retrieved_source", from_id=added_subtask.subtask_id, to_id=source.source_id), EvidenceGraphEdge(run_id=empty_graph.run_id, relation="source_contains_evidence", from_id=source.source_id, to_id=original_unit.evidence_id), EvidenceGraphEdge(run_id=empty_graph.run_id, relation="source_contains_evidence", from_id=source.source_id, to_id=unit.evidence_id), EvidenceGraphEdge(run_id=empty_graph.run_id, relation="evidence_supports_subtask", from_id=original_unit.evidence_id, to_id=original_subtask.subtask_id), EvidenceGraphEdge(run_id=empty_graph.run_id, relation="evidence_supports_subtask", from_id=unit.evidence_id, to_id=added_subtask.subtask_id)), key=lambda item: (item.relation, item.from_id, item.to_id))))
    assessment = asyncio.run(assess_evidence_graph(graph, (), AssessmentContext(completed_subtask_ids=tuple(item.subtask_id for item in replanned.plan.subtasks))))
    writer = FakeWriter(_draft(task, brief, replanned.plan, graph, claims=[_claim(unit.evidence_id, unit.verbatim_content)]))
    result = asyncio.run(SingleWriterRunner(writer, budget=spec).run(task, brief, approval, replanned.plan, graph, assessment, event_path=tmp_path / "replan.jsonl", checkpoint_path=tmp_path / "replan.checkpoint.json"))
    assert result.validation.status is ReportStatus.complete
    assert decide_replan(empty_assessment, result.ledger, spec, original_plan_id=plan.plan_id).outcome.value == "budget_exhausted"


def test_writer_schemas_are_stable_utf8_lf_and_match_committed_files(tmp_path: Path):
    written = write_writer_schemas(tmp_path)
    committed = Path("docs/deep_research/writer/v1")
    for name, path in written.items():
        assert path.read_bytes() == (committed / name).read_bytes()
        assert b"\r\n" not in path.read_bytes()
    assert render_writer_schemas() == {name: (committed / name).read_text(encoding="utf-8") for name in written}
