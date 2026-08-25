from __future__ import annotations

import json

import pytest

from litflow.agent.durable_events import DurableEventError, DurableEventLog, render_planner_request, replay_planner_requests, run_fake_durable_validation
from litflow.agent.live import NativeToolPlanner, agent_tool_definitions
from litflow.agent.runtime import ResearchAgent
from litflow.agent.tools import FakeAgentTools
from litflow.llm.client import LLMToolCompletion


def test_parallel_tool_batch_has_ordered_call_result_pairs_and_replayable_request(tmp_path):
    log = DurableEventLog.create(tmp_path / "log", turn_id="turn-1", task_id="AG01", run_identity={"prompt_sha": "p", "policy_sha": "x", "task_set_sha": "t", "git_sha": "g"})
    allowed = [{"function": {"name": "answer_grounded"}}]
    task = {"task_id": "AG01", "task_zh": "中文问题"}
    first = render_planner_request(log.load_verified_events(), log.projection(), allowed, task=task)
    log.record_provider_step(step_id="step-1", model="fake", model_call_ordinal=1, request_payload={"messages": first["messages"], "tools": first["tools"]}, tool_calls=[
        {"tool_call_id": "provider-a", "tool_name": "retrieve_evidence", "args": {"query": "A"}},
        {"tool_call_id": "provider-b", "tool_name": "inspect_passages", "args": {"passage_ids": ["P:1"]}},
    ])
    log.record_tool_result("provider-a", result_status="success", internal_result={"evidence_ids": ["P:1"]}, model_visible_content=json.dumps({"message": "检索到证据 P:1", "evidence_refs": ["P:1"]}, ensure_ascii=False))
    log.record_tool_result("provider-b", result_status="success", internal_result={"passage_ids": ["P:1"]}, model_visible_content=json.dumps({"message": "检查了 P:1"}, ensure_ascii=False))

    events = log.load_verified_events()
    assert [event["event_type"] for event in events if event["event_type"] in {"tool_call", "tool_result"}] == ["tool_call", "tool_call", "tool_result", "tool_result"]
    assert log.projection()["completed_tool_call_ids"] == ["provider-a", "provider-b"]
    online = render_planner_request(events, log.projection(), allowed, task=task)
    log.record_provider_step(step_id="step-2", model="fake", model_call_ordinal=2, request_payload={"messages": online["messages"], "tools": online["tools"]}, tool_calls=[])
    replayed = replay_planner_requests(log.path, allowed, task=task)
    assert online["request_sha256"] == replayed["requests"][-1]["request_sha256"]
    assert "检索到证据 P:1" in online["messages"][1]["content"]


def test_terminal_denied_invalid_and_execution_error_results_are_required(tmp_path):
    log = DurableEventLog.create(tmp_path / "log", turn_id="turn-2", task_id="AG02", run_identity={})
    log.record_provider_step(step_id="step-1", model="fake", model_call_ordinal=1, request_payload={"messages": [], "tools": []}, tool_calls=[
        {"tool_name": "retrieve_evidence", "args": {"query": "x"}},
        {"tool_name": "inspect_passages", "args": {"passage_ids": ["P:1"]}},
        {"tool_name": "answer_grounded", "args": {"query_id": "AG02"}},
    ])
    calls = [event for event in log.load_verified_events() if event["event_type"] == "tool_call"]
    log.record_tool_result(calls[0]["tool_call_id"], result_status="denied", internal_result={}, model_visible_content="Denied")
    log.record_tool_result(calls[1]["tool_call_id"], result_status="invalid_arguments", internal_result={}, model_visible_content="Invalid")
    log.record_tool_result(calls[2]["tool_call_id"], result_status="execution_error", internal_result={}, model_visible_content="Error")
    assert log.validate_terminal_results() is True


def test_synthetic_tool_call_ids_and_hash_chain_are_deterministic_and_corruption_fails_closed(tmp_path):
    log = DurableEventLog.create(tmp_path / "log", turn_id="turn-3", task_id="AG03", run_identity={})
    log.record_provider_step(step_id="step-1", model="fake", model_call_ordinal=1, request_payload={"messages": [], "tools": []}, tool_calls=[{"tool_name": "retrieve_evidence", "args": {"top_k": 10, "query": "RGB-D"}}])
    call = next(event for event in log.load_verified_events() if event["event_type"] == "tool_call")
    assert call["tool_call_id_source"] == "deterministic_synthetic"
    assert len(call["args_sha256"]) == 64
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write('{"event_seq":999}\n')
    with pytest.raises(DurableEventError, match="hash chain"):
        log.load_verified_events()


def test_result_ref_cannot_replace_model_visible_content_and_projection_mismatch_fails_closed(tmp_path):
    log = DurableEventLog.create(tmp_path / "log", turn_id="turn-4", task_id="AG04", run_identity={})
    with pytest.raises(DurableEventError, match="model_visible_content"):
        log.record_tool_result("missing", result_status="success", internal_result={"ref": "only"}, model_visible_content="")
    log.record_provider_step(step_id="step-1", model="fake", model_call_ordinal=1, request_payload={"messages": [], "tools": []}, tool_calls=[{"tool_name": "query_evidence_matrix", "args": {}}])
    call = next(event for event in log.load_verified_events() if event["event_type"] == "tool_call")
    log.record_tool_result(call["tool_call_id"], result_status="success", internal_result={"record_ids": ["R1"]}, model_visible_content="Matrix record R1")
    with pytest.raises(DurableEventError, match="state_projection_mismatch"):
        log.verify_projection({"completed_tool_call_ids": []})


def test_fake_runtime_uses_durable_renderer_and_records_tool_result_for_replay(tmp_path):
    class FakeProvider:
        model = "fake"

        def __init__(self):
            self.calls = 0

        def complete_tools_with_usage(self, _messages, _tools, **_kwargs):
            self.calls += 1
            calls = [{"id": "provider-call", "function": {"name": "retrieve_evidence", "arguments": '{"query":"WT-C3k2"}'}}] if self.calls == 1 else []
            return LLMToolCompletion(content="", tool_calls=calls, input_tokens=1, output_tokens=1, total_tokens=2)

    log = DurableEventLog.create(tmp_path / "durable", turn_id="turn-5", task_id="AG01", run_identity={})
    task = {"task_id": "AG01", "task_zh": "解释 WT-C3k2"}
    agent = ResearchAgent(FakeAgentTools(), NativeToolPlanner(FakeProvider(), task, event_log=log), checkpoint_dir=tmp_path / "traces", event_log=log)
    agent.run(task["task_zh"], thread_id="AG01")

    assert log.validate_terminal_results() is True
    replay = replay_planner_requests(log.path, agent_tool_definitions(), task=task)
    assert len(replay["requests"]) == 2
    assert "P1:C1" in replay["requests"][1]["messages"][1]["content"]


def test_durable_events_reject_qrels_and_credentials_and_legacy_trace_is_nonreplayable(tmp_path):
    log = DurableEventLog.create(tmp_path / "log", turn_id="turn-6", task_id="AG06", run_identity={})
    with pytest.raises(DurableEventError, match="forbidden content"):
        log.record_planner_request({"messages": [{"role": "user", "content": "gold_evidence_summary"}], "tools": []})
    with pytest.raises(DurableEventError, match="forbidden content"):
        log.record_planner_request({"messages": [{"role": "user", "content": "Authorization: Bearer secret"}], "tools": []})


def test_fake_durable_validation_writes_replayable_artifact_without_llm(tmp_path):
    result = run_fake_durable_validation(tmp_path / "validation")

    assert result["external_llm_called"] is False
    assert result["canonical_request_replay"] is True
    assert (tmp_path / "validation" / "validation_summary.json").is_file()
