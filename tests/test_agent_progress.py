from litflow.agent.progress import ProgressController, extract_requested_entities
from litflow.agent.durable_events import DurableEventLog
from litflow.agent.live import NativeToolPlanner
from litflow.agent.runtime import AgentRunConfig, ResearchAgent
from litflow.agent.tools import FakeAgentTools
from litflow.llm.client import LLMToolCompletion


def test_progress_controller_limits_retrieval_and_exposes_answer_after_evidence():
    controller = ProgressController({"entities": [{"entity_name": "Merge-YOLO", "aliases": ["Merge-YOLO"], "paper_key": "P1"}]})
    entities = extract_requested_entities("说明 Merge-YOLO 与 Imaginary-Detector-X", controller.entity_metadata)
    assert controller.retrieval_limit(entities) == 2
    initial = controller.next_actions({"retrieved_evidence_count": 0, "retrieval_calls_used": 0, "evidence_matrix_loaded": False, "approval_status": "not_requested"}, category="single_paper", requested_entities=entities)
    assert "retrieve_evidence" in initial
    after = controller.next_actions({"retrieved_evidence_count": 1, "retrieval_calls_used": 2, "evidence_matrix_loaded": False, "approval_status": "not_requested"}, category="single_paper", requested_entities=entities)
    assert "retrieve_evidence" not in after
    assert "answer_grounded" in after


def test_progress_fingerprint_ignores_repeated_evidence_and_routes_partial_none_complete():
    controller = ProgressController({"entities": []})
    base = {"successful_tool_signatures": ["a"], "retrieved_evidence_ids": ["P:1"], "covered_entities": ["A"], "missing_entities": ["B"], "evidence_matrix_loaded": False, "approval_status": "not_requested", "final_answer_status": None}
    assert controller.fingerprint(base) == controller.fingerprint({**base, "retrieved_evidence_ids": ["P:1", "P:1"]})
    assert controller.coverage_route({**base, "retrieved_evidence_count": 1}) == "partial"
    assert controller.coverage_route({**base, "missing_entities": [], "retrieved_evidence_count": 1}) == "complete"
    assert controller.coverage_route({**base, "retrieved_evidence_count": 0, "covered_entities": []}) == "none"


def test_steering_is_single_use_and_has_no_gold_or_task_specific_data():
    controller = ProgressController({"entities": []})
    message = controller.steering_message({"retrieved_evidence_count": 1, "covered_entities": ["A"], "missing_entities": ["B"], "retrieval_calls_remaining": 0, "tool_calls_remaining": 3, "allowed_next_actions": ["answer_grounded"], "steering_used": False})
    assert message is not None
    assert "qrels" not in message.casefold()
    assert "gold" not in message.casefold()
    assert controller.steering_message({"steering_used": True}) is None


def test_fake_ag01_uses_soft_limit_then_steers_to_answer_without_hard_failure(tmp_path):
    class Provider:
        model = "fake"
        def __init__(self): self.index = 0
        def complete_tools_with_usage(self, _messages, _tools, **_kwargs):
            names = ["retrieve_evidence", "retrieve_evidence", "answer_grounded"]
            name = names[self.index]; self.index += 1
            args = ('{"query":"Merge-YOLO"}' if self.index == 1 else '{"query":"WT-C3k2"}') if name == "retrieve_evidence" else '{"query_id":"AG01"}'
            return LLMToolCompletion(content="", tool_calls=[{"id": f"c{self.index}", "function": {"name": name, "arguments": args}}])
    metadata = {"entities": [{"entity_name": "Merge-YOLO", "aliases": ["Merge-YOLO"], "paper_key": "P"}]}
    controller = ProgressController(metadata)
    task = {"task_id": "AG01", "category": "single_paper", "task_zh": "说明 Merge-YOLO"}
    log = DurableEventLog.create(tmp_path / "events", turn_id="t", task_id="AG01", run_identity={}, initial_projection={"missing_entities": ["Merge-YOLO"]})
    agent = ResearchAgent(FakeAgentTools(), NativeToolPlanner(Provider(), task, event_log=log, progress_controller=controller, requested_entities=["Merge-YOLO"]), checkpoint_dir=tmp_path / "trace", event_log=log, progress_controller=controller, task_category="single_paper", requested_entities=["Merge-YOLO"], config=AgentRunConfig(max_retrieval_calls=3))
    result = agent.run(task["task_zh"], thread_id="AG01")
    assert result["final_status"] == "complete"
    assert any(event["event_type"] == "steering" for event in log.load_verified_events())


def test_fake_ag11_interrupts_after_one_matrix_query_without_writing(tmp_path):
    class Provider:
        model = "fake"
        def complete_tools_with_usage(self, *_args, **_kwargs):
            return LLMToolCompletion(content="", tool_calls=[{"id": "matrix-1", "function": {"name": "query_evidence_matrix", "arguments": "{}"}}])
    controller = ProgressController({"entities": []})
    task = {"task_id": "AG11", "category": "writing_approval", "task_zh": "生成草稿"}
    log = DurableEventLog.create(tmp_path / "events", turn_id="t", task_id="AG11", run_identity={})
    tools = FakeAgentTools()
    agent = ResearchAgent(tools, NativeToolPlanner(Provider(), task, event_log=log, progress_controller=controller), checkpoint_dir=tmp_path / "trace", event_log=log, progress_controller=controller, task_category="writing_approval")
    result = agent.run(task["task_zh"], thread_id="AG11")
    assert result["final_status"] == "pending_approval"
    assert [call["tool_name"] for call in tools.calls] == ["query_evidence_matrix"]
    resumed = agent.resume("AG11", approved=True)
    assert resumed["final_status"] == "complete"
    assert [call["tool_name"] for call in tools.calls] == ["query_evidence_matrix", "stage_writing_draft"]
    events = log.load_verified_events()
    provider_result_ids = [event["tool_call_id"] for event in events if event["event_type"] == "tool_result"]
    scheduled = next(event for event in events if event["event_type"] == "internal_action_scheduled")
    assert provider_result_ids == ["matrix-1"]
    assert scheduled["action_origin"] == "internal_control_plane"
    assert scheduled["internal_action_id"] != "matrix-1"
    assert sum(event["event_type"] == "internal_action_result" for event in events) == 1


def test_fake_ag11_reject_writes_decision_without_internal_action(tmp_path):
    class Provider:
        model = "fake"
        def complete_tools_with_usage(self, *_args, **_kwargs):
            return LLMToolCompletion(content="", tool_calls=[{"id": "matrix-1", "function": {"name": "query_evidence_matrix", "arguments": "{}"}}])
    controller = ProgressController({"entities": []})
    task = {"task_id": "AG11", "category": "writing_approval", "task_zh": "生成草稿"}
    log = DurableEventLog.create(tmp_path / "events", turn_id="t", task_id="AG11", run_identity={})
    tools = FakeAgentTools()
    agent = ResearchAgent(tools, NativeToolPlanner(Provider(), task, event_log=log, progress_controller=controller), checkpoint_dir=tmp_path / "trace", event_log=log, progress_controller=controller, task_category="writing_approval")
    agent.run(task["task_zh"], thread_id="AG11")
    result = agent.resume("AG11", approved=False)
    assert result["final_status"] == "author_rejected"
    assert [call["tool_name"] for call in tools.calls] == ["query_evidence_matrix"]
    assert not any(event["event_type"] == "internal_action_scheduled" for event in log.load_verified_events())


def test_fake_ag07_routes_to_partial_answer_without_claim_for_missing_entity(tmp_path):
    class Provider:
        model = "fake"
        def __init__(self): self.index = 0
        def complete_tools_with_usage(self, *_args, **_kwargs):
            names = ["retrieve_evidence", "retrieve_evidence", "retrieve_evidence", "answer_grounded"]
            name = names[self.index]; self.index += 1
            args = f'{{"query":"entity{self.index}"}}' if name == "retrieve_evidence" else '{"query_id":"AG07"}'
            return LLMToolCompletion(content="", tool_calls=[{"id": f"c{self.index}", "function": {"name": name, "arguments": args}}])
    class PartialTools(FakeAgentTools):
        def __init__(self): super().__init__(); self.retrievals = 0
        def execute(self, name, args):
            self.calls.append({"tool_name": name, "args": args})
            if name == "retrieve_evidence":
                self.retrievals += 1
                return {"evidence_refs": [f"P:C{self.retrievals}"] if self.retrievals < 3 else [], "passages": []}
            if name == "answer_grounded":
                return {"coverage_status": "partial", "verified_claim_ids": ["C1", "C2"], "evidence_refs": ["P:C1", "P:C2"], "qa_result": {"coverage_ledger": {"covered_entities": [{"entity_name": "Merge-YOLO"}, {"entity_name": "Improved YOLOv8"}], "uncovered_entities": [{"entity_name": "Imaginary-Detector-X"}]}}}
            raise AssertionError(name)
    controller = ProgressController({"entities": []})
    entities = ["Merge-YOLO", "Improved YOLOv8", "Imaginary-Detector-X"]
    task = {"task_id": "AG07", "category": "partial_coverage", "task_zh": "compare entities"}
    log = DurableEventLog.create(tmp_path / "events", turn_id="t", task_id="AG07", run_identity={}, initial_projection={"missing_entities": entities})
    tools = PartialTools()
    agent = ResearchAgent(tools, NativeToolPlanner(Provider(), task, event_log=log, progress_controller=controller, requested_entities=entities), checkpoint_dir=tmp_path / "trace", event_log=log, progress_controller=controller, task_category="partial_coverage", requested_entities=entities, config=AgentRunConfig(max_retrieval_calls=3))
    result = agent.run(task["task_zh"], thread_id="AG07")
    assert result["final_status"] == "partial"
    assert log.projection()["missing_entities"] == ["Imaginary-Detector-X"]
    assert [call["tool_name"] for call in tools.calls] == ["retrieve_evidence", "retrieve_evidence", "retrieve_evidence", "answer_grounded"]
