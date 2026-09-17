from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime

import pytest

from litflow.deep_research.budgets import BudgetSpec
from litflow.deep_research.contracts import BriefApproval, BriefApprovalStatus, ResearchBrief, ResearchTask
from litflow.deep_research.executor import EvidenceCandidate, EvidenceGraph, EvidenceGraphEdge, ExecutorError, LocalResearchExecutor, ReadOnlyToolRegistry, ToolName
from litflow.deep_research.planner import FakePlanner, PlannerDraft, PlannerSubtaskDraft, plan_approved_brief
from litflow.deep_research.schema_export import render_executor_schemas, write_executor_schemas
from litflow.deep_research.runtime_v2 import replay_runtime_events
from litflow.deep_research.state import RunState
from litflow.deep_research.policies import CancellationToken


NOW = datetime(2026, 9, 7, tzinfo=UTC)


def _inputs():
    task = ResearchTask.create("Which local evidence supports alpha?", "en", ("local-only",), "grounded_report", NOW)
    brief = ResearchBrief.create(task.task_id, "Find local alpha evidence.", ("alpha",), (), "evidence", ("quote",), ("local-only",), BriefApprovalStatus.approved)
    approval = BriefApproval.create(brief.brief_id, task.task_id, BriefApprovalStatus.approved, "human", NOW)
    draft = PlannerDraft(task_id=task.task_id, brief_id=brief.brief_id, locale="en", constraints=brief.constraints, scope_inclusions=brief.scope_inclusions, scope_exclusions=brief.scope_exclusions, subtasks=(
        PlannerSubtaskDraft(local_key="find", question="alpha evidence", rationale="find", expected_evidence=("quote",), completion_criteria=("one",)),
        PlannerSubtaskDraft(local_key="relate", question="alpha relation", rationale="relate", dependencies=("find",), expected_evidence=("quote",), completion_criteria=("one",)),
    ))
    plan = asyncio.run(plan_approved_brief(task, brief, approval, FakePlanner(draft)))
    return task, brief, approval, plan


def _corpus():
    text = "Alpha evidence is preserved in this local passage."
    return [{"passage_id": "P1:P1_chunk_0001", "paper_key": "P1", "citation_key": "cite", "title": "Paper", "chunk_id": "P1_chunk_0001", "page_start": 1, "page_end": 1, "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "source_context_sha256": "a" * 64}]


def test_approved_plan_runs_in_topological_order_and_builds_stable_evidence_graph(tmp_path):
    task, brief, approval, plan = _inputs()
    registry = ReadOnlyToolRegistry(_corpus())
    executor = LocalResearchExecutor(registry)
    result = asyncio.run(executor.execute(task, brief, approval, plan, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert [item.subtask_id for item in result.subtask_results] == list(plan.topological_subtask_ids)
    assert len(result.evidence_graph.evidence_units) == 1
    assert {edge.relation for edge in result.evidence_graph.edges} == {"subtask_retrieved_source", "source_contains_evidence", "evidence_supports_subtask"}
    assert registry.calls == [ToolName.search_local_corpus, ToolName.read_passage, ToolName.search_local_corpus, ToolName.read_passage]
    assert replay_runtime_events(RunState(run_id=result.run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True), result.events, executor._budget).journal.records


@pytest.mark.parametrize("candidate", [EvidenceCandidate(passage_id="P1:P1_chunk_0001", quote_hint="missing"), EvidenceCandidate(passage_id="P2:missing", quote_hint="Alpha")])
def test_bad_anchor_or_cross_passage_fails_closed(tmp_path, candidate):
    task, brief, approval, plan = _inputs()
    registry = ReadOnlyToolRegistry(_corpus())
    with pytest.raises(ExecutorError, match="evidence_anchor_not_found|passage_not_found"):
        asyncio.run(LocalResearchExecutor(registry).execute(task, brief, approval, plan, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "checkpoint.json", candidates={plan.subtasks[0].subtask_id: (candidate,)}))


def test_unapproved_plan_never_calls_tools(tmp_path):
    task, brief, approval, plan = _inputs()
    registry = ReadOnlyToolRegistry(_corpus())
    brief = brief.model_copy(update={"approval_status": BriefApprovalStatus.rejected})
    with pytest.raises(ExecutorError, match="plan_not_executable"):
        asyncio.run(LocalResearchExecutor(registry).execute(task, brief, approval, plan, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert registry.calls == []


def test_registry_rejects_unavailable_capability_and_path_is_not_a_request(tmp_path):
    registry = ReadOnlyToolRegistry(_corpus(), allowed=(ToolName.search_local_corpus,))
    from litflow.deep_research.executor import ReadPassageRequest
    with pytest.raises(ExecutorError, match="tool_not_allowed"):
        asyncio.run(registry.invoke(ToolName.read_passage, ReadPassageRequest(passage_id="C:\\secret.txt")))
    assert registry.calls == []


def test_budget_exhaustion_happens_before_tool_call(tmp_path):
    task, brief, approval, plan = _inputs()
    registry = ReadOnlyToolRegistry(_corpus())
    with pytest.raises(ExecutorError, match="budget_exhausted"):
        asyncio.run(LocalResearchExecutor(registry, budget=BudgetSpec(max_tool_calls=0, max_retries=0, max_replans=0, run_timeout_s=30, operation_timeout_s=10)).execute(task, brief, approval, plan, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert registry.calls == []


def test_graph_rejects_duplicate_and_cross_run_edges(tmp_path):
    task, brief, approval, plan = _inputs()
    result = asyncio.run(LocalResearchExecutor(ReadOnlyToolRegistry(_corpus())).execute(task, brief, approval, plan, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    edge = result.evidence_graph.edges[0]
    with pytest.raises(ValueError, match="duplicate edge"):
        EvidenceGraph.model_validate({**result.evidence_graph.model_dump(mode="json"), "edges": [edge.model_dump(mode="json"), edge.model_dump(mode="json")]})
    with pytest.raises(ValueError, match="invalid edge"):
        EvidenceGraph.model_validate({**result.evidence_graph.model_dump(mode="json"), "edges": [{**edge.model_dump(mode="json"), "run_id": "dr-run-" + "f" * 24}]})


def test_schema_exports_are_stable_utf8_lf_and_match_committed_files(tmp_path):
    written = write_executor_schemas(tmp_path)
    committed = __import__("pathlib").Path("docs/deep_research/executor/v1")
    for name, target in written.items():
        assert target.read_bytes() == (committed / name).read_bytes()
        assert b"\r\n" not in target.read_bytes()
    assert render_executor_schemas() == {name: (committed / name).read_text(encoding="utf-8") for name in written}


def test_timeout_after_dispatch_is_unknown_and_never_replayed(tmp_path, monkeypatch):
    task, brief, approval, plan = _inputs()
    registry = ReadOnlyToolRegistry(_corpus())

    async def slow_call(name, request):
        await asyncio.sleep(.1)

    monkeypatch.setattr(registry, "invoke", slow_call)
    executor = LocalResearchExecutor(registry, budget=BudgetSpec(max_tool_calls=4, max_retries=0, max_replans=0, run_timeout_s=1, operation_timeout_s=.001))
    with pytest.raises(ExecutorError, match="unknown_outcome"):
        asyncio.run(executor.execute(task, brief, approval, plan, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    from litflow.deep_research.runtime_v2 import UnifiedEventStore
    events = UnifiedEventStore(tmp_path / "events.jsonl", run_id=__import__("litflow.deep_research.identity", fromlist=["make_stable_id"]).make_stable_id("run", {"runtime": "dr-local-research-executor-v1", "plan_id": plan.plan_id})).read_all()
    assert events[-1].event_type.value == "operation_unknown"
    calls_before_replay = list(registry.calls)
    replay_runtime_events(RunState(run_id=events[0].run_id, task_id=task.task_id, brief_id=brief.brief_id, brief_approved=True), events, executor._budget)
    assert registry.calls == calls_before_replay == []


def test_cancelled_executor_never_dispatches_a_tool(tmp_path):
    task, brief, approval, plan = _inputs()
    token = CancellationToken()
    token.request()
    registry = ReadOnlyToolRegistry(_corpus())
    with pytest.raises(ExecutorError, match="cancelled"):
        asyncio.run(LocalResearchExecutor(registry, token=token).execute(task, brief, approval, plan, event_path=tmp_path / "events.jsonl", checkpoint_path=tmp_path / "checkpoint.json"))
    assert registry.calls == []


def test_same_inputs_produce_stable_evidence_and_graph(tmp_path):
    task, brief, approval, plan = _inputs()
    first = asyncio.run(LocalResearchExecutor(ReadOnlyToolRegistry(_corpus())).execute(task, brief, approval, plan, event_path=tmp_path / "first.jsonl", checkpoint_path=tmp_path / "first.checkpoint.json"))
    second = asyncio.run(LocalResearchExecutor(ReadOnlyToolRegistry(_corpus())).execute(task, brief, approval, plan, event_path=tmp_path / "second.jsonl", checkpoint_path=tmp_path / "second.checkpoint.json"))
    assert first.run_id == second.run_id
    assert first.evidence_graph == second.evidence_graph
