from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from litflow.deep_research.budgets import BudgetSpec
from litflow.deep_research.contracts import BriefApproval, BriefApprovalStatus, ResearchBrief, ResearchTask
from litflow.deep_research.e2e import E2ETerminalError, GLME2ECrossPaperAttemptPlan, GLMSingleWriter, DeepResearchRunner, _validate_cross_paper_allowlist, parse_e2e_pilot_plan, preflight_e2e_pilot, require_cross_paper_comparison, runtime_source_sha256
from litflow.deep_research.executor import EvidenceCandidate, ExecutorError, LocalResearchExecutor, LocalSearchRequest, ReadOnlyToolRegistry, ToolName
from litflow.deep_research.gap_replan import AssessmentContext, assess_evidence_graph
from litflow.deep_research.planner import FakePlanner, PlannerDraft, PlannerSubtaskDraft, plan_approved_brief
from litflow.deep_research.runtime_v2 import RuntimeEventType, UnifiedEventStore
from litflow.deep_research.writer import FakeWriter, ReportDraft, ReportStatus, SingleWriterRunner, WriterError, validate_report_draft


NOW = datetime(2026, 9, 10, tzinfo=UTC)


def _corpus() -> list[dict[str, object]]:
    rows = [json.loads(line) for line in Path("outputs/rag_bm25_v1/passages.jsonl").read_text(encoding="utf-8").splitlines() if line]
    selected = []
    for paper, passage in (("L4DLHQUZ", "L4DLHQUZ:L4DLHQUZ_chunk_0007"), ("3NLKTSIP", "3NLKTSIP:3NLKTSIP_chunk_0005")):
        row = next(item for item in rows if item["passage_id"] == passage)
        assert row["paper_key"] == paper
        selected.append(row)
    return selected


def _full_corpus() -> list[dict[str, object]]:
    return [json.loads(line) for line in Path("outputs/rag_bm25_v1/passages.jsonl").read_text(encoding="utf-8").splitlines() if line]


def _inputs(tmp_path: Path):
    task = ResearchTask.create("How do selected local papers describe their approaches to multi-scale feature handling?", "en", ("local-only", "cross-paper"), "grounded_report", NOW)
    brief = ResearchBrief.create(task.task_id, "Compare only explicitly grounded method descriptions from selected local papers.", ("method comparison",), (), "grounded report", ("one comparison grounded claim",), task.constraints, BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "human", NOW)
    draft = PlannerDraft(task_id=task.task_id, brief_id=brief.brief_id, locale="en", constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions, subtasks=(
        PlannerSubtaskDraft(local_key="paper_a", question="retrieve TPMN multi-level feature fusion", rationale="capture source A method details", expected_evidence=("method passage",), completion_criteria=("one grounded result",)),
        PlannerSubtaskDraft(local_key="paper_b", question="retrieve multi-scale convolutional feature fusion", rationale="capture source B method details", expected_evidence=("method passage",), completion_criteria=("one grounded result",)),
    ))
    plan = asyncio.run(plan_approved_brief(task, brief, approval, FakePlanner(draft)))
    spec = BudgetSpec(max_provider_calls=1, max_provider_attempts=1, max_tool_calls=8, max_tool_attempts=8, max_retries=0, max_replans=0, run_timeout_s=90, operation_timeout_s=30)
    registry = ReadOnlyToolRegistry(_corpus())
    executor = LocalResearchExecutor(registry, budget=spec)
    candidates = {plan.subtasks[0].subtask_id: (EvidenceCandidate(passage_id="L4DLHQUZ:L4DLHQUZ_chunk_0007", quote_hint=next(x["text"] for x in _corpus() if x["paper_key"] == "L4DLHQUZ")),), plan.subtasks[1].subtask_id: (EvidenceCandidate(passage_id="3NLKTSIP:3NLKTSIP_chunk_0005", quote_hint=next(x["text"] for x in _corpus() if x["paper_key"] == "3NLKTSIP")),)}
    executed = asyncio.run(executor.execute(task, brief, approval, plan, event_path=tmp_path / "tools.jsonl", checkpoint_path=tmp_path / "tools.checkpoint.json", candidates=candidates, run_id="dr-run-cross-paper-test"))
    assessment = asyncio.run(assess_evidence_graph(executed.evidence_graph, (), AssessmentContext(completed_subtask_ids=tuple(item.subtask_id for item in plan.subtasks))))
    return task, brief, approval, plan, executed.evidence_graph, assessment, spec, registry


def _draft(task, brief, plan, graph, *, both: bool = True):
    units = list(graph.evidence_units)
    citations = [{"evidence_id": units[0].evidence_id, "quote": units[0].verbatim_content, "relation": "support"}]
    if both:
        citations.append({"evidence_id": units[1].evidence_id, "quote": units[1].verbatim_content, "relation": "support"})
    return ReportDraft.model_validate({"schema_version": "dr-report-draft-v1", "task_id": task.task_id, "brief_id": brief.brief_id, "plan_id": plan.plan_id, "run_id": graph.run_id, "sections": [{"heading": "Comparison", "claims": [{"text": "The two papers use distinct multi-scale feature handling strategies.", "language": "en", "citations": citations}]}]})


def test_frozen_corpus_has_two_distinct_sources_and_real_passages(tmp_path: Path):
    task, brief, approval, plan, graph, assessment, spec, registry = _inputs(tmp_path)
    assert len(graph.sources) == 2 and len({item.source_id for item in graph.sources}) == 2
    assert len(graph.evidence_units) == 2 and {item.source_id for item in graph.evidence_units} == {item.source_id for item in graph.sources}
    assert all(item.locator.passage_id and item.locator.page_number and item.locator.span_start is not None and item.locator.span_end is not None for item in graph.evidence_units)


def test_cross_paper_claim_requires_two_source_citations(tmp_path: Path):
    task, brief, approval, plan, graph, assessment, spec, registry = _inputs(tmp_path)
    passing = validate_report_draft(task, brief, approval, plan, graph, assessment, _draft(task, brief, plan, graph))
    assert passing.status is ReportStatus.complete
    require_cross_paper_comparison(graph, passing)
    failing = validate_report_draft(task, brief, approval, plan, graph, assessment, _draft(task, brief, plan, graph, both=False))
    with pytest.raises(WriterError, match="cross_paper_comparison_invalid"):
        require_cross_paper_comparison(graph, failing)


def test_cross_paper_runner_persists_gate_failure_without_external_calls(tmp_path: Path):
    task, brief, approval, plan, graph, assessment, spec, registry = _inputs(tmp_path)
    writer = FakeWriter(_draft(task, brief, plan, graph, both=False).model_dump(mode="json"))
    with pytest.raises(WriterError, match="cross_paper_comparison_invalid"):
        asyncio.run(SingleWriterRunner(writer, budget=spec).run(task, brief, approval, plan, graph, assessment, event_path=tmp_path / "writer.jsonl", checkpoint_path=tmp_path / "writer.checkpoint.json", validation_guard=require_cross_paper_comparison))
    events = UnifiedEventStore(tmp_path / "writer.jsonl", run_id=graph.run_id).read_all()
    assert writer.calls == 1 and any(event.event_type is RuntimeEventType.operation_failed and event.payload.get("operation_name") == "single_writer" for event in events)


def test_executor_allowlist_excludes_unselected_retrieval_results(tmp_path: Path):
    task, brief, approval, plan, _, _, spec, registry = _inputs(tmp_path)
    registry = ReadOnlyToolRegistry(_full_corpus())
    candidates = {plan.subtasks[0].subtask_id: (EvidenceCandidate(passage_id="L4DLHQUZ:L4DLHQUZ_chunk_0007", quote_hint=next(x["text"] for x in _corpus() if x["paper_key"] == "L4DLHQUZ")),), plan.subtasks[1].subtask_id: (EvidenceCandidate(passage_id="3NLKTSIP:3NLKTSIP_chunk_0005", quote_hint=next(x["text"] for x in _corpus() if x["paper_key"] == "3NLKTSIP")),)}
    allowed_passages = tuple(row["passage_id"] for row in _full_corpus() if row["paper_key"] in {"L4DLHQUZ", "3NLKTSIP"})
    result = asyncio.run(LocalResearchExecutor(registry, budget=spec).execute(task, brief, approval, plan, event_path=tmp_path / "allow.jsonl", checkpoint_path=tmp_path / "allow.checkpoint.json", candidates=candidates, run_id="dr-run-cross-allow", allowed_source_keys=("L4DLHQUZ", "3NLKTSIP"), allowed_passage_ids=allowed_passages))
    assert {source.bibliographic_metadata["paper_key"] for source in result.evidence_graph.sources} == {"L4DLHQUZ", "3NLKTSIP"}


def test_executor_rejects_unselected_candidate_before_evidence_graph(tmp_path: Path):
    task, brief, approval, plan, _, _, spec, _ = _inputs(tmp_path)
    registry = ReadOnlyToolRegistry(_full_corpus())
    bad = {plan.subtasks[0].subtask_id: (EvidenceCandidate(passage_id="Q55RU9N6:Q55RU9N6_chunk_0008", quote_hint="wrong source"),), plan.subtasks[1].subtask_id: (EvidenceCandidate(passage_id="3NLKTSIP:3NLKTSIP_chunk_0005", quote_hint=next(x["text"] for x in _corpus() if x["paper_key"] == "3NLKTSIP")),)}
    allowed_passages = tuple(row["passage_id"] for row in _full_corpus() if row["paper_key"] in {"L4DLHQUZ", "3NLKTSIP"})
    with pytest.raises(ExecutorError, match="cross_paper_source_selection_mismatch"):
        asyncio.run(LocalResearchExecutor(registry, budget=spec).execute(task, brief, approval, plan, event_path=tmp_path / "bad.jsonl", checkpoint_path=tmp_path / "bad.checkpoint.json", candidates=bad, run_id="dr-run-cross-bad", allowed_source_keys=("L4DLHQUZ", "3NLKTSIP"), allowed_passage_ids=allowed_passages))


def test_source_scope_is_applied_before_bm25_ranking():
    full = _full_corpus()
    registry = ReadOnlyToolRegistry(full, allowed_source_keys=("L4DLHQUZ",), allowed_passage_ids=("L4DLHQUZ:L4DLHQUZ_chunk_0007",))
    hits = asyncio.run(registry.invoke(ToolName.search_local_corpus, LocalSearchRequest(query="retrieve explicitly grounded method descriptions from local source L4DLHQUZ")))
    assert hits and hits[0].passage_id == "L4DLHQUZ:L4DLHQUZ_chunk_0007"
    assert registry.last_search_stats == {"pre_filter_candidate_count": len(full), "source_scoped_candidate_count": 1, "source_scoped_result_count": 1, "bounded_top_k": 1}


def test_cross_allowlist_reports_missing_selected_source(tmp_path: Path):
    _, _, _, _, graph, _, _, _ = _inputs(tmp_path)
    one_source = graph.model_copy(update={"sources": (graph.sources[0],), "evidence_units": tuple(unit for unit in graph.evidence_units if unit.source_id == graph.sources[0].source_id), "edges": tuple(edge for edge in graph.edges if edge.from_id in {graph.sources[0].source_id, graph.evidence_units[0].evidence_id} or edge.to_id in {graph.sources[0].source_id, graph.evidence_units[0].evidence_id})})
    with pytest.raises(ExecutorError, match="cross_paper_source_selection_mismatch"):
        _validate_cross_paper_allowlist(one_source, ("L4DLHQUZ", "3NLKTSIP"), ("L4DLHQUZ:L4DLHQUZ_chunk_0007", "3NLKTSIP:3NLKTSIP_chunk_0005"))


def test_executor_known_failure_is_terminalized_by_e2e_runner(tmp_path: Path):
    task = ResearchTask.create("How do selected local papers describe their approaches to multi-scale feature handling?", "en", ("local-only", "cross-paper"), "grounded_report", NOW)
    brief = ResearchBrief.create(task.task_id, "Compare only explicitly grounded method descriptions from selected local papers.", ("method comparison",), (), "grounded report", ("one comparison grounded claim",), task.constraints, BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "human", NOW)
    draft = PlannerDraft(task_id=task.task_id, brief_id=brief.brief_id, locale="en", constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions, subtasks=(PlannerSubtaskDraft(local_key="paper_a", question="retrieve explicitly grounded method descriptions from local source 3NLKTSIP", rationale="collect source A", expected_evidence=("quote",), completion_criteria=("one",)),))
    spec = BudgetSpec(max_provider_calls=1, max_provider_attempts=1, max_tool_calls=8, max_tool_attempts=8, max_retries=0, max_replans=0, run_timeout_s=90, operation_timeout_s=30)
    registry = ReadOnlyToolRegistry(_full_corpus())
    writer = FakeWriter({})
    runner = DeepResearchRunner(FakePlanner(draft), LocalResearchExecutor(registry, budget=spec), writer, budget=spec, comparison_required=True, allowed_source_keys=("L4DLHQUZ", "3NLKTSIP"), allowed_passage_ids=("L4DLHQUZ:L4DLHQUZ_chunk_0007", "3NLKTSIP:3NLKTSIP_chunk_0005"))
    with pytest.raises(Exception) as failure:
        asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / "runtime.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert getattr(failure.value, "error_code", None) == "selected_source_evidence_missing"
    events = UnifiedEventStore(tmp_path / "runtime.jsonl", run_id=DeepResearchRunner.run_id(task, brief)).read_all()
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert events[-1].event_type is RuntimeEventType.lifecycle_transition and events[-1].payload["to_status"] == "failed" and events[-1].payload["terminal_reason"] == "selected_source_evidence_missing"
    assert checkpoint["run_state"]["status"] == "failed" and checkpoint["stream_head"] == events[-1].event_hash
    failed = next(event for event in events if event.event_type is RuntimeEventType.elapsed_recorded and event.payload.get("stage_failure"))
    assert failed.payload["stage_failure"]["contract_error_code"] == "selected_source_evidence_missing"
    assert writer.calls == 0 and registry.calls == [ToolName.search_local_corpus]


def test_executor_unknown_failure_is_terminalized_without_writer(tmp_path: Path):
    task = ResearchTask.create("local unknown probe", "en", ("local-only",), "grounded_report", NOW)
    brief = ResearchBrief.create(task.task_id, "Probe local evidence.", ("local",), (), "grounded report", ("one quote",), task.constraints, BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "human", NOW)
    draft = PlannerDraft(task_id=task.task_id, brief_id=brief.brief_id, locale="en", constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions, subtasks=(PlannerSubtaskDraft(local_key="probe", question="probe", rationale="probe", expected_evidence=("quote",), completion_criteria=("one",)),))
    spec = BudgetSpec(max_provider_calls=1, max_provider_attempts=1, max_tool_calls=8, max_tool_attempts=8, max_retries=0, max_replans=0, run_timeout_s=90, operation_timeout_s=30)
    class UnknownRegistry:
        calls = []
        async def invoke(self, name, request):
            self.calls.append(name)
            raise TimeoutError()
    registry = UnknownRegistry()
    writer = FakeWriter({})
    runner = DeepResearchRunner(FakePlanner(draft), LocalResearchExecutor(registry, budget=spec), writer, budget=spec)
    with pytest.raises(E2ETerminalError) as failure:
        asyncio.run(runner.run(task, brief, approval, event_path=tmp_path / "runtime.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert failure.value.error_code == "unknown_outcome" and failure.value.outcome_unknown
    events = UnifiedEventStore(tmp_path / "runtime.jsonl", run_id=DeepResearchRunner.run_id(task, brief)).read_all()
    checkpoint = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert any(event.event_type is RuntimeEventType.operation_unknown for event in events)
    assert checkpoint["run_state"]["status"] == "failed" and checkpoint["run_state"]["terminal_reason"] == "unknown_outcome"
    assert checkpoint["stream_head"] == events[-1].event_hash and writer.calls == 0


def test_cross_plan_preflight_binds_selected_sources_and_task_input():
    plan = parse_e2e_pilot_plan(json.loads(Path("docs/deep_research/e2e/v1.2/glm_e2e_cross_paper_plan.attempt-002.json").read_text(encoding="utf-8")))
    assert isinstance(plan, GLME2ECrossPaperAttemptPlan)
    current_item = plan.tasks[0].model_copy(update={"implementation_commit_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "runtime_source_sha256": runtime_source_sha256(), "artifact_dir": "outputs/deep_research/e2e/v1.2/dr-run-111111111111111111111111"})
    current_plan = plan.model_copy(update={"tasks": [current_item]})
    assert len(preflight_e2e_pilot(current_plan, repo_root=Path.cwd())) == 1
    bad = current_plan.model_copy(update={"tasks": [current_item.model_copy(update={"selected_source_keys": ["Q55RU9N6", "3NLKTSIP"]})]})
    with pytest.raises(ValueError, match="task input"):
        preflight_e2e_pilot(bad, repo_root=Path.cwd())
