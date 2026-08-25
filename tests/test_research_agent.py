from __future__ import annotations

from litflow.agent.runtime import AgentRunConfig, FakePlanner, ResearchAgent, replay_agent_trace
from litflow.agent.tools import FakeAgentTools
from litflow.agent.evaluation import evaluate_agent_traces


def test_fake_agent_completes_retrieve_inspect_answer_with_trace_and_budget(tmp_path):
    tools = FakeAgentTools()
    planner = FakePlanner([
        {"tool_name": "list_papers", "args": {}},
        {"tool_name": "retrieve_evidence", "args": {"query": "WT-C3k2", "top_k": 3}},
        {"tool_name": "inspect_passages", "args": {"passage_ids": ["P1:C1"]}},
        {"tool_name": "answer_grounded", "args": {"query_id": "Q1"}},
        {"tool_name": "finish", "args": {}},
    ])
    agent = ResearchAgent(tools, planner, checkpoint_dir=tmp_path)

    result = agent.run("Explain WT-C3k2", thread_id="t1")

    assert result["final_status"] == "complete"
    assert result["coverage_status"] == "complete"
    assert [item["tool_name"] for item in result["tool_calls"]] == ["list_papers", "retrieve_evidence", "inspect_passages", "answer_grounded"]
    assert result["tool_call_count"] == 4
    assert result["model_call_count"] == 4
    assert all(item["guardrail"]["allowed"] for item in result["tool_calls"])
    assert (tmp_path / "t1" / "trace.json").is_file()


def test_policy_gate_blocks_forbidden_qrels_unknown_tool_and_inspect_limit(tmp_path):
    tools = FakeAgentTools()
    planner = FakePlanner([
        {"tool_name": "read_qrels", "args": {}},
    ])
    agent = ResearchAgent(tools, planner, checkpoint_dir=tmp_path)
    result = agent.run("unsafe", thread_id="t2")
    assert result["final_status"] == "execution_failed"
    assert result["failure_reason"] == "tool_not_allowed"
    assert result["tool_call_count"] == 0

    planner = FakePlanner([{"tool_name": "inspect_passages", "args": {"passage_ids": ["P1:C1", "P1:C2", "P1:C3", "P1:C4"]}}])
    result = ResearchAgent(tools, planner, checkpoint_dir=tmp_path).run("too many", thread_id="t3")
    assert result["final_status"] == "execution_failed"
    assert result["failure_reason"] == "tool_arguments_invalid"


def test_repeated_call_and_budget_circuit_breakers_terminate(tmp_path):
    tools = FakeAgentTools()
    repeated = FakePlanner([
        {"tool_name": "list_papers", "args": {}},
        {"tool_name": "list_papers", "args": {}},
    ])
    result = ResearchAgent(tools, repeated, checkpoint_dir=tmp_path).run("repeat", thread_id="t4")
    assert result["final_status"] == "execution_failed"
    assert result["failure_reason"] == "repeated_tool_call"

    budget = FakePlanner([
        {"tool_name": "list_papers", "args": {"title_keyword": "one"}},
        {"tool_name": "list_papers", "args": {"title_keyword": "two"}},
        {"tool_name": "list_papers", "args": {"title_keyword": "three"}},
    ])
    result = ResearchAgent(tools, budget, checkpoint_dir=tmp_path, config=AgentRunConfig(max_model_turns=2)).run("budget", thread_id="t5")
    assert result["final_status"] == "execution_failed"
    assert result["failure_reason"] == "model_turn_budget_exceeded"


def test_stage_writing_interrupt_requires_approval_and_resume(tmp_path):
    tools = FakeAgentTools()
    planner = FakePlanner([
        {"tool_name": "stage_writing_draft", "args": {"record_ids": ["R1"]}},
        {"tool_name": "finish", "args": {}},
    ])
    agent = ResearchAgent(tools, planner, checkpoint_dir=tmp_path)
    paused = agent.run("prepare writing", thread_id="t6")
    assert paused["final_status"] == "pending_approval"
    assert paused["pending_approval"]["tool_name"] == "stage_writing_draft"
    assert tools.calls == []

    resumed = agent.resume("t6", approved=True)
    assert resumed["final_status"] == "complete"
    assert [call["tool_name"] for call in tools.calls] == ["stage_writing_draft"]


def test_replay_uses_trace_without_planner_or_tools(tmp_path):
    tools = FakeAgentTools()
    planner = FakePlanner([{ "tool_name": "finish", "args": {}}])
    agent = ResearchAgent(tools, planner, checkpoint_dir=tmp_path)
    result = agent.run("finish", thread_id="t7")
    replay = replay_agent_trace(tmp_path / "t7" / "trace.json")
    assert replay["external_llm_called"] is False
    assert replay["replay_capability"] == "legacy_nonreplayable"
    assert replay["final_status"] == result["final_status"]


def test_trace_evaluator_reports_frozen_safety_metrics(tmp_path):
    result = ResearchAgent(FakeAgentTools(), FakePlanner([{ "tool_name": "finish", "args": {}}]), checkpoint_dir=tmp_path).run("finish", thread_id="t8")
    metrics = evaluate_agent_traces([result])
    assert metrics["tool_argument_valid_rate"] == 1.0
    assert metrics["unsafe_action_count"] == 0
    assert metrics["loop_termination_rate"] == 1.0


def test_tool_execution_error_terminates_as_execution_failure(tmp_path):
    class FailingTools(FakeAgentTools):
        def execute(self, _name, _args):
            raise ValueError("frozen input unavailable")

    agent = ResearchAgent(FailingTools(), FakePlanner([{"tool_name": "retrieve_evidence", "args": {"query": "x"}}]), checkpoint_dir=tmp_path)
    result = agent.run("retrieve", thread_id="tool-error")

    assert result["final_status"] == "execution_failed"
    assert result["failure_reason"] == "tool_execution_failed"
