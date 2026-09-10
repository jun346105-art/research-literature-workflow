from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from litflow.deep_research.contracts import BriefApproval, BriefApprovalStatus, EvidenceLocator, EvidenceModality, EvidenceUnit, ResearchBrief, ResearchTask, Source, SourceKind
from litflow.deep_research.e2e import GLME2EInsufficientEvidenceAttemptPlan, parse_e2e_pilot_plan, preflight_e2e_pilot, write_e2e_insufficient_evidence_schema
from litflow.deep_research.executor import EvidenceGraph, EvidenceGraphEdge
from litflow.deep_research.gap_replan import AssessmentContext, SubtaskEvidenceRequirement, assess_evidence_graph
from litflow.deep_research.identity import sha256_hex
from litflow.deep_research.planner import FakePlanner, PlannerDraft, PlannerSubtaskDraft, plan_approved_brief
from litflow.deep_research.runtime_v2 import CoordinatedCheckpointV2, replay_runtime_events
from litflow.deep_research.state import RunState, RunStatus
from litflow.deep_research.writer import FakeWriter, ReportDraft, ReportStatus, SingleWriterRunner, validate_report_draft


NOW = datetime(2026, 9, 10, tzinfo=UTC)


def _inputs(*, with_evidence: bool = False):
    task = ResearchTask.create("What was the orbital inclination and propellant mass of the Mars Reconnaissance Orbiter mission?", "en", ("local-only", "insufficient-evidence"), "grounded_report", NOW)
    brief = ResearchBrief.create(task.task_id, "Answer only when the frozen local corpus contains direct mission evidence; otherwise abstain.", ("mission orbital parameters",), (), "grounded report", ("no unsupported claim",), task.constraints, BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "human", NOW)
    draft = PlannerDraft(task_id=task.task_id, brief_id=brief.brief_id, locale=task.locale, constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions, subtasks=(PlannerSubtaskDraft(local_key="search", question="search the frozen local corpus for direct mission parameters", rationale="verify whether the corpus supports the approved question", expected_evidence=("direct mission parameter passage",), completion_criteria=("abstain when absent",)),))
    plan = asyncio.run(plan_approved_brief(task, brief, approval, FakePlanner(draft)))
    subtask = plan.subtasks[0]
    if not with_evidence:
        graph = EvidenceGraph(run_id="dr-run-insufficient-test", task_id=task.task_id, plan_id=plan.plan_id, subtasks=(subtask,), sources=(), evidence_units=(), edges=())
    else:
        source = Source.create(SourceKind.passage_corpus, "corpus:P1:" + "a" * 64, "Local paper", "a" * 64, "en", bibliographic_metadata={"paper_key": "P1"})
        unit = EvidenceUnit.create(source.source_id, EvidenceModality.text, EvidenceLocator(passage_id="P1:P1_chunk_0001", page_number=1, span_start=0, span_end=24), "Unrelated local evidence only.", "en")
        graph = EvidenceGraph(run_id="dr-run-insufficient-test", task_id=task.task_id, plan_id=plan.plan_id, subtasks=(subtask,), sources=(source,), evidence_units=(unit,), edges=(EvidenceGraphEdge(run_id="dr-run-insufficient-test", relation="evidence_supports_subtask", from_id=unit.evidence_id, to_id=subtask.subtask_id), EvidenceGraphEdge(run_id="dr-run-insufficient-test", relation="source_contains_evidence", from_id=source.source_id, to_id=unit.evidence_id), EvidenceGraphEdge(run_id="dr-run-insufficient-test", relation="subtask_retrieved_source", from_id=subtask.subtask_id, to_id=source.source_id)))
    return task, brief, approval, plan, graph


def test_insufficient_plan_schema_restricts_task_and_terminal():
    assert GLME2EInsufficientEvidenceAttemptPlan.model_fields["schema_version"].default == "dr-glm-e2e-pilot-v1.2-insufficient-evidence"
    assert GLME2EInsufficientEvidenceAttemptPlan.model_fields["tasks"].annotation


def test_insufficient_schema_is_canonical_and_byte_stable(tmp_path: Path):
    first = write_e2e_insufficient_evidence_schema(tmp_path / "one").read_bytes()
    second = write_e2e_insufficient_evidence_schema(tmp_path / "two").read_bytes()
    assert first == second and b"\r\n" not in first
    assert json.loads(first)["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_insufficient_attempt_plan_passes_offline_preflight():
    plan = parse_e2e_pilot_plan(json.loads(Path("docs/deep_research/e2e/v1.2/glm_e2e_insufficient_evidence_plan.attempt-002.json").read_text(encoding="utf-8")))
    assert isinstance(plan, GLME2EInsufficientEvidenceAttemptPlan)
    assert plan.tasks[0].attempt_id == "glm-5.3-flash-deepresearch-insufficient-evidence-002"
    assert plan.tasks[0].expected_terminal == "insufficient_evidence"
    assert len(preflight_e2e_pilot(plan, repo_root=Path.cwd())) == 1


def test_empty_evidence_requires_structured_abstention():
    task, brief, approval, plan, graph = _inputs()
    assessment = asyncio.run(assess_evidence_graph(graph, (), AssessmentContext(completed_subtask_ids=(plan.subtasks[0].subtask_id,))))
    draft = ReportDraft.model_validate({"schema_version": "dr-report-draft-v1", "task_id": task.task_id, "brief_id": brief.brief_id, "plan_id": plan.plan_id, "run_id": graph.run_id, "abstention_reason": "The frozen corpus contains no direct mission evidence.", "sections": [{"heading": "Insufficient evidence", "claims": []}]})
    result = validate_report_draft(task, brief, approval, plan, graph, assessment, draft)
    assert result.status is ReportStatus.insufficient_evidence
    assert result.report is not None and not result.report.claims and not result.report.publication_ready


def test_small_grounded_subset_is_partial_when_scope_remains_uncovered():
    task, brief, approval, plan, graph = _inputs(with_evidence=True)
    unit = graph.evidence_units[0]
    assessment = asyncio.run(assess_evidence_graph(graph, (SubtaskEvidenceRequirement(subtask_id=plan.subtasks[0].subtask_id, required_scope_labels=("mission",)),), AssessmentContext(completed_subtask_ids=(plan.subtasks[0].subtask_id,))))
    draft = ReportDraft.model_validate({"schema_version": "dr-report-draft-v1", "task_id": task.task_id, "brief_id": brief.brief_id, "plan_id": plan.plan_id, "run_id": graph.run_id, "sections": [{"heading": "Verified local fragment", "claims": [{"text": "The local fragment is not sufficient to answer the mission question.", "language": "en", "citations": [{"evidence_id": unit.evidence_id, "quote": unit.verbatim_content, "relation": "support"}]}]}]})
    result = validate_report_draft(task, brief, approval, plan, graph, assessment, draft)
    assert result.status is ReportStatus.partial
    assert result.report is not None and len(result.report.claims) == 1 and len(result.report.citations) == 1


def test_writer_abstention_is_durable_and_replay_is_zero_call(tmp_path: Path):
    task, brief, approval, plan, graph = _inputs()
    assessment = asyncio.run(assess_evidence_graph(graph, (), AssessmentContext(completed_subtask_ids=(plan.subtasks[0].subtask_id,))))
    writer = FakeWriter({"sections": [{"heading": "Insufficient evidence", "claims": []}], "abstention_reason": "No direct mission evidence in the frozen corpus."})
    runner = SingleWriterRunner(writer)
    result = asyncio.run(runner.run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "runtime.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert writer.calls == 1 and result.validation.status is ReportStatus.insufficient_evidence
    assert result.validation.report is not None and result.validation.report.author_review_required and not result.validation.report.publication_ready
    initial = RunState(run_id=graph.run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True)
    replay = replay_runtime_events(initial, list(result.events), runner._budget)
    assert replay.run_state.status is RunStatus.insufficient_evidence and writer.calls == 1
    assert CoordinatedCheckpointV2.model_validate_json((tmp_path / "checkpoint.json").read_text(encoding="utf-8")).run_state.status is RunStatus.insufficient_evidence


def test_frozen_corpus_has_no_direct_mars_mission_terms():
    corpus = Path("outputs/rag_bm25_v1/passages.jsonl").read_text(encoding="utf-8").lower()
    assert all(term not in corpus for term in ("mars", "orbital", "propellant", "orbiter"))
    assert sha256_hex(corpus.encode("utf-8"))
