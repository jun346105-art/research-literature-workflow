from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from litflow.agent.tools import AgentToolError, FakeAgentTools, TOOL_PERMISSIONS, canonical_tool_signature, validate_tool_args


class ResearchAgentState(TypedDict, total=False):
    run_id: str
    thread_id: str
    user_goal: str
    task_type: str
    plan: list[str]
    current_step: int
    tool_calls: list[dict[str, Any]]
    evidence_refs: list[str]
    inspected_passage_ids: list[str]
    verified_claim_ids: list[str]
    coverage_status: str
    missing_entities: list[str]
    model_call_count: int
    tool_call_count: int
    repeated_call_count: int
    input_tokens: int
    output_tokens: int
    pending_approval: dict[str, Any] | None
    final_status: str | None
    final_artifact: str | None
    failure_reason: str | None
    planned_action: dict[str, Any] | None
    last_tool_name: str | None
    last_tool_result: dict[str, Any] | None
    approval_decision: bool | None
    tool_signatures: list[str]
    trace: list[dict[str, Any]]


@dataclass(frozen=True)
class AgentRunConfig:
    max_model_turns: int = 4
    max_tool_calls: int = 6
    max_retrieval_calls: int = 2
    same_tool_same_args_repeat: int = 1


class Planner(Protocol):
    def decide(self, state: ResearchAgentState) -> dict[str, Any]: ...


@dataclass
class FakePlanner:
    actions: list[dict[str, Any]]
    index: int = 0

    def decide(self, state: ResearchAgentState) -> dict[str, Any]:
        if self.index >= len(self.actions):
            return {"tool_name": "finish", "args": {}, "decision_summary": "No more fake actions."}
        action = self.actions[self.index]
        self.index += 1
        return {**action, "decision_summary": action.get("decision_summary", f"Fake planner selected {action['tool_name']}.")}


class ResearchAgent:
    def __init__(self, tools: FakeAgentTools, planner: Planner, *, checkpoint_dir: Path, config: AgentRunConfig | None = None) -> None:
        self.tools = tools
        self.planner = planner
        self.checkpoint_dir = checkpoint_dir
        self.config = config or AgentRunConfig()
        self.checkpointer = InMemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ResearchAgentState)
        graph.add_node("intake_guardrail", self._intake_guardrail)
        graph.add_node("planner", self._planner)
        graph.add_node("policy_gate", self._policy_gate)
        graph.add_node("tool_executor", self._tool_executor)
        graph.add_node("evidence_verifier", self._evidence_verifier)
        graph.add_node("coverage_router", self._coverage_router)
        graph.add_node("human_approval", self._human_approval)
        graph.add_node("finalizer", self._finalizer)
        graph.add_edge(START, "intake_guardrail")
        graph.add_edge("intake_guardrail", "planner")
        graph.add_edge("planner", "policy_gate")
        graph.add_conditional_edges("policy_gate", self._after_policy, {"execute": "tool_executor", "approve": "human_approval", "finish": "finalizer", "failed": "finalizer"})
        graph.add_edge("tool_executor", "evidence_verifier")
        graph.add_edge("evidence_verifier", "coverage_router")
        graph.add_conditional_edges("coverage_router", self._after_coverage, {"replan": "planner", "finish": "finalizer", "failed": "finalizer"})
        graph.add_conditional_edges("human_approval", self._after_approval, {"execute": "tool_executor", "finish": "finalizer"})
        graph.add_edge("finalizer", END)
        return graph.compile(checkpointer=self.checkpointer)

    def run(self, user_goal: str, *, thread_id: str) -> dict[str, Any]:
        state: ResearchAgentState = {"run_id": thread_id, "thread_id": thread_id, "user_goal": user_goal, "task_type": "unknown", "plan": [], "current_step": 0, "tool_calls": [], "evidence_refs": [], "inspected_passage_ids": [], "verified_claim_ids": [], "coverage_status": "none", "missing_entities": [], "model_call_count": 0, "tool_call_count": 0, "repeated_call_count": 0, "input_tokens": 0, "output_tokens": 0, "pending_approval": None, "final_status": None, "final_artifact": None, "failure_reason": None, "planned_action": None, "last_tool_name": None, "last_tool_result": None, "approval_decision": None, "tool_signatures": [], "trace": []}
        result = self.graph.invoke(state, self._config(thread_id))
        values = self._state_values(thread_id, result)
        self._persist(values)
        return values

    def resume(self, thread_id: str, *, approved: bool) -> dict[str, Any]:
        result = self.graph.invoke(Command(resume=approved), self._config(thread_id))
        values = self._state_values(thread_id, result)
        self._persist(values)
        return values

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def _state_values(self, thread_id: str, result: dict[str, Any]) -> dict[str, Any]:
        values = dict(self.graph.get_state(self._config(thread_id)).values)
        values.update({key: value for key, value in result.items() if key != "__interrupt__"})
        if result.get("__interrupt__"):
            values["final_status"] = "pending_approval"
        return values

    def _trace(self, state: ResearchAgentState, node: str, **data: Any) -> dict[str, Any]:
        return {"trace": [*state["trace"], {"node": node, **data}]}

    def _intake_guardrail(self, state: ResearchAgentState) -> dict[str, Any]:
        if not state["user_goal"].strip():
            return {**self._trace(state, "intake_guardrail", outcome="failed", reason="empty_goal"), "final_status": "execution_failed", "failure_reason": "empty_goal"}
        return {**self._trace(state, "intake_guardrail", outcome="allowed"), "task_type": "research_task"}

    def _planner(self, state: ResearchAgentState) -> dict[str, Any]:
        if state["model_call_count"] >= self.config.max_model_turns:
            return {**self._trace(state, "planner", outcome="failed", reason="model_turn_budget_exceeded"), "final_status": "execution_failed", "failure_reason": "model_turn_budget_exceeded"}
        action = self.planner.decide(state)
        return {**self._trace(state, "planner", action=action.get("tool_name"), decision_summary=action.get("decision_summary", "")), "planned_action": action, "model_call_count": state["model_call_count"] + 1, "current_step": state["current_step"] + 1}

    def _policy_gate(self, state: ResearchAgentState) -> dict[str, Any]:
        if state.get("final_status") == "execution_failed":
            return self._trace(state, "policy_gate", allowed=False, reason=state.get("failure_reason"))
        action = state.get("planned_action") or {}
        name = action.get("tool_name")
        if name == "finish":
            return {**self._trace(state, "policy_gate", tool_name="finish", allowed=True), "planned_action": {"tool_name": "finish", "args": {}}}
        if name not in TOOL_PERMISSIONS:
            return {**self._trace(state, "policy_gate", tool_name=name, allowed=False, reason="tool_not_allowed"), "final_status": "execution_failed", "failure_reason": "tool_not_allowed"}
        try:
            args = validate_tool_args(name, action.get("args") or {})
        except AgentToolError as exc:
            return {**self._trace(state, "policy_gate", tool_name=name, allowed=False, reason=str(exc)), "final_status": "execution_failed", "failure_reason": str(exc)}
        if state["tool_call_count"] >= self.config.max_tool_calls:
            return {**self._trace(state, "policy_gate", tool_name=name, allowed=False, reason="tool_call_budget_exceeded"), "final_status": "execution_failed", "failure_reason": "tool_call_budget_exceeded"}
        if name == "retrieve_evidence" and sum(item["tool_name"] == name for item in state["tool_calls"]) >= self.config.max_retrieval_calls:
            return {**self._trace(state, "policy_gate", tool_name=name, allowed=False, reason="retrieval_budget_exceeded"), "final_status": "execution_failed", "failure_reason": "retrieval_budget_exceeded"}
        signature = canonical_tool_signature(name, args)
        if signature in state["tool_signatures"]:
            return {**self._trace(state, "policy_gate", tool_name=name, allowed=False, reason="repeated_tool_call"), "final_status": "execution_failed", "failure_reason": "repeated_tool_call", "repeated_call_count": state["repeated_call_count"] + 1}
        pending = {"tool_name": name, "args": args} if TOOL_PERMISSIONS[name] == "approval_required" else None
        return {**self._trace(state, "policy_gate", tool_name=name, args=args, allowed=True, permission=TOOL_PERMISSIONS[name]), "planned_action": {"tool_name": name, "args": args}, "tool_signatures": [*state["tool_signatures"], signature], "pending_approval": pending}

    def _after_policy(self, state: ResearchAgentState) -> str:
        if state.get("final_status") == "execution_failed": return "failed"
        if (state.get("planned_action") or {}).get("tool_name") == "finish": return "finish"
        if state.get("pending_approval"): return "approve"
        return "execute"

    def _tool_executor(self, state: ResearchAgentState) -> dict[str, Any]:
        action = state["planned_action"]
        try:
            result = self.tools.execute(action["tool_name"], action["args"])
        except Exception as exc:
            return {
                **self._trace(state, "tool_executor", tool_name=action["tool_name"], outcome="failed", error_type=type(exc).__name__),
                "final_status": "execution_failed",
                "failure_reason": "tool_execution_failed",
                "last_tool_name": action["tool_name"],
                "last_tool_result": {"execution_status": "tool_execution_failed"},
            }
        record = {"tool_name": action["tool_name"], "args": action["args"], "permission": TOOL_PERMISSIONS[action["tool_name"]], "guardrail": {"allowed": True}, "result_refs": result.get("evidence_refs", result.get("passages", result.get("record_ids", [])))}
        return {**self._trace(state, "tool_executor", tool_name=action["tool_name"], result_ref_count=len(record["result_refs"])), "tool_calls": [*state["tool_calls"], record], "tool_call_count": state["tool_call_count"] + 1, "last_tool_name": action["tool_name"], "last_tool_result": result, "pending_approval": None}

    def _evidence_verifier(self, state: ResearchAgentState) -> dict[str, Any]:
        result = state.get("last_tool_result") or {}
        update: dict[str, Any] = self._trace(state, "evidence_verifier", outcome="observed")
        if "evidence_refs" in result: update["evidence_refs"] = [*state["evidence_refs"], *result["evidence_refs"]]
        if "passages" in result: update["inspected_passage_ids"] = [*state["inspected_passage_ids"], *[item["passage_id"] for item in result["passages"] if "passage_id" in item]]
        if "verified_claim_ids" in result:
            update["verified_claim_ids"] = [*state["verified_claim_ids"], *result["verified_claim_ids"]]
            update["coverage_status"] = result.get("coverage_status", "none")
        return update

    def _coverage_router(self, state: ResearchAgentState) -> dict[str, Any]:
        if state.get("coverage_status") == "execution_failed":
            return {**self._trace(state, "coverage_router", route="failed"), "final_status": "execution_failed"}
        if state.get("last_tool_name") in {"answer_grounded", "stage_writing_draft"}:
            return self._trace(state, "coverage_router", route="finish", coverage=state.get("coverage_status"))
        return self._trace(state, "coverage_router", route="replan", coverage=state.get("coverage_status"))

    def _after_coverage(self, state: ResearchAgentState) -> str:
        if state.get("final_status") == "execution_failed":
            return "failed"
        return "finish" if state.get("last_tool_name") in {"answer_grounded", "stage_writing_draft"} else "replan"

    def _human_approval(self, state: ResearchAgentState) -> dict[str, Any]:
        approved = interrupt({"tool_name": state["pending_approval"]["tool_name"], "args": state["pending_approval"]["args"], "reason": "stage_writing_draft requires human approval"})
        return {**self._trace(state, "human_approval", approved=bool(approved)), "approval_decision": bool(approved)}

    def _after_approval(self, state: ResearchAgentState) -> str:
        return "execute" if state.get("approval_decision") else "finish"

    def _finalizer(self, state: ResearchAgentState) -> dict[str, Any]:
        status = state.get("final_status")
        if status is None:
            status = "complete" if state.get("last_tool_name") == "stage_writing_draft" or state.get("coverage_status") in {"complete", "partial"} else "insufficient_evidence"
        return {**self._trace(state, "finalizer", final_status=status), "final_status": status, "final_artifact": f"{state['thread_id']}/trace.json"}

    def _persist(self, state: dict[str, Any]) -> None:
        directory = self.checkpoint_dir / state["thread_id"]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "trace.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replay_agent_trace(path: Path) -> dict[str, Any]:
    state = json.loads(path.read_text(encoding="utf-8"))
    return {"external_llm_called": False, "thread_id": state["thread_id"], "final_status": state.get("final_status"), "tool_call_count": state.get("tool_call_count"), "trace": state.get("trace", [])}
