"""Append-only v2 events for replayable, model-visible Agent state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DurableEventError(ValueError):
    pass


TRACE_SCHEMA_VERSION = 2
PLANNER_SYSTEM_PROMPT = (
    "You are a bounded research workflow planner. Use only the provided native tools. "
    "Never request qrels, gold answers, files, shell, network, credentials, or side effects outside tools. "
    "Select exactly one tool when useful; otherwise return no tool call. "
    "Do not answer the user yourself. Use answer_grounded only after retrieve_evidence. "
    "Use stage_writing_draft only after query_evidence_matrix and only when the runtime grants approval."
)


@dataclass
class DurableEventLog:
    path: Path
    turn_id: str
    task_id: str

    @classmethod
    def create(cls, root: Path, *, turn_id: str, task_id: str, run_identity: dict[str, Any]) -> DurableEventLog:
        root.mkdir(parents=True, exist_ok=False)
        log = cls(root / "events.jsonl", turn_id, task_id)
        log._append("turn_started", {"turn_id": turn_id, "task_id": task_id, "trace_schema_version": TRACE_SCHEMA_VERSION, "run_identity": run_identity})
        return log

    def record_provider_step(self, *, step_id: str, model: str, model_call_ordinal: int, request_payload: dict[str, Any], tool_calls: list[dict[str, Any]], provider_request_id: str | None = None, usage: dict[str, int | None] | None = None, latency_ms: float | None = None, finish_reason: str | None = None, request_event_seq: int | None = None) -> None:
        self._append("provider_step", {
            "turn_id": self.turn_id,
            "step_id": step_id,
            "step_ordinal": model_call_ordinal,
            "provider_request_id": provider_request_id,
            "model": model,
            "model_call_ordinal": model_call_ordinal,
            "input_tokens": (usage or {}).get("input_tokens"),
            "output_tokens": (usage or {}).get("output_tokens"),
            "total_tokens": (usage or {}).get("total_tokens"),
            "latency_ms": latency_ms,
            "finish_reason": finish_reason,
            "request_event_seq": request_event_seq,
            "rendered_messages_sha256": _sha(_canonical(request_payload.get("messages", []))),
            "rendered_tools_sha256": _sha(_canonical(request_payload.get("tools", []))),
            "rendered_request_sha256": _sha(_canonical(request_payload)),
            "request_payload": request_payload,
        })
        batch_id = _sha(_canonical({"turn_id": self.turn_id, "step_id": step_id, "tool_calls": tool_calls}))[:24]
        self._append("tool_batch", {"tool_batch_id": batch_id, "turn_id": self.turn_id, "step_id": step_id, "tool_call_count": len(tool_calls), "original_model_order": list(range(1, len(tool_calls) + 1)), "batch_status": "proposed"})
        for ordinal, call in enumerate(tool_calls, 1):
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            args_json = _canonical(args)
            provided = call.get("tool_call_id")
            tool_name = call.get("tool_name")
            if not isinstance(tool_name, str) or not tool_name:
                raise DurableEventError("tool call requires tool_name")
            call_id = provided if isinstance(provided, str) and provided else _synthetic_call_id(step_id, ordinal, tool_name, _sha(args_json))
            self._append("tool_call", {"tool_batch_id": batch_id, "tool_call_id": call_id, "tool_call_id_source": "provider" if provided else "deterministic_synthetic", "ordinal_in_batch": ordinal, "tool_name": tool_name, "canonical_args_json": args_json, "args_sha256": _sha(args_json), "policy_decision": "pending", "execution_status": "pending", "started_at": None, "completed_at": None, "latency_ms": None})

    def record_planner_request(self, request_payload: dict[str, Any]) -> int:
        """Persist the canonical pre-provider request before dispatch."""
        event = self._append("provider_request", {
            "messages": request_payload["messages"],
            "tools": request_payload["tools"],
            "rendered_messages_sha256": _sha(_canonical(request_payload["messages"])),
            "rendered_tools_sha256": _sha(_canonical(request_payload["tools"])),
            "rendered_request_sha256": _sha(_canonical(request_payload)),
        })
        return event["event_seq"]

    def calls_for_step(self, step_id: str) -> list[dict[str, Any]]:
        return [event for event in self.load_verified_events() if event["event_type"] == "tool_call" and self._step_for_batch(event["tool_batch_id"]) == step_id]

    def record_tool_result(self, tool_call_id: str, *, result_status: str, internal_result: dict[str, Any], model_visible_content: str, verification_status: str = "not_applicable", policy_status: str = "allowed", error_code: str | None = None) -> None:
        if result_status not in {"success", "denied", "invalid_arguments", "execution_error", "skipped_due_to_budget", "skipped_due_to_prior_failure", "cancelled"}:
            raise DurableEventError("invalid terminal tool result status")
        if not model_visible_content:
            raise DurableEventError("model_visible_content is required")
        calls = {event["tool_call_id"] for event in self.load_verified_events() if event["event_type"] == "tool_call"}
        if tool_call_id not in calls:
            raise DurableEventError("tool result references unknown call")
        results = {event["tool_call_id"] for event in self.load_verified_events() if event["event_type"] == "tool_result"}
        if tool_call_id in results:
            raise DurableEventError("tool call already has terminal result")
        self._append("tool_result", {"tool_call_id": tool_call_id, "tool_batch_id": self._batch_for_call(tool_call_id), "result_status": result_status, "internal_result_ref": None, "internal_result_sha256": _sha(_canonical(internal_result)), "model_visible_content": model_visible_content, "model_visible_content_sha256": _sha(model_visible_content), "verification_status": verification_status, "policy_status": policy_status, "error_code": error_code, "created_at": _timestamp()})

    def load_verified_events(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            raise DurableEventError("durable event log is missing")
        previous = None
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DurableEventError("durable event JSON is corrupted") from exc
            if event.get("event_seq") != len(events) + 1 or event.get("previous_event_sha256") != previous:
                raise DurableEventError("event hash chain is broken")
            actual = event.get("event_sha256")
            payload = {key: value for key, value in event.items() if key != "event_sha256"}
            if actual != _sha(_canonical(payload)):
                raise DurableEventError("event hash chain is broken")
            previous = actual
            events.append(event)
        return events

    def validate_terminal_results(self) -> bool:
        events = self.load_verified_events()
        calls = [event["tool_call_id"] for event in events if event["event_type"] == "tool_call"]
        results = [event["tool_call_id"] for event in events if event["event_type"] == "tool_result"]
        if sorted(calls) != sorted(results) or len(results) != len(set(results)):
            raise DurableEventError("every tool call requires exactly one terminal result")
        return True

    def projection(self) -> dict[str, Any]:
        return project_events(self.load_verified_events())

    def verify_projection(self, checkpoint_state: dict[str, Any]) -> None:
        projection = self.projection()
        for key in ("completed_tool_call_ids", "successful_tool_signatures", "retrieved_evidence_ids", "retrieved_evidence_count", "evidence_matrix_loaded"):
            if key in checkpoint_state and checkpoint_state[key] != projection[key]:
                raise DurableEventError("state_projection_mismatch")

    def _batch_for_call(self, tool_call_id: str) -> str:
        for event in self.load_verified_events():
            if event["event_type"] == "tool_call" and event["tool_call_id"] == tool_call_id:
                return event["tool_batch_id"]
        raise DurableEventError("tool result references unknown call")

    def _step_for_batch(self, batch_id: str) -> str:
        for event in self.load_verified_events():
            if event["event_type"] == "tool_batch" and event["tool_batch_id"] == batch_id:
                return event["step_id"]
        raise DurableEventError("tool batch is missing")

    def _append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        _assert_safe_payload(payload)
        events = self.load_verified_events() if self.path.exists() else []
        previous = events[-1]["event_sha256"] if events else None
        event = {"event_seq": len(events) + 1, "event_type": event_type, "previous_event_sha256": previous, **payload, "created_at": payload.get("created_at", _timestamp())}
        event["event_sha256"] = _sha(_canonical(event))
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical(event) + "\n")
            handle.flush()
        return event


def project_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [event for event in events if event["event_type"] == "tool_call"]
    results = [event for event in events if event["event_type"] == "tool_result"]
    successful = [item for item in results if item["result_status"] == "success"]
    signatures = []
    retrieved_ids = []
    matrix_loaded = False
    call_by_id = {event["tool_call_id"]: event for event in calls}
    for result in successful:
        call = call_by_id[result["tool_call_id"]]
        signatures.append(_sha(call["tool_name"] + call["canonical_args_json"]))
        if call["tool_name"] == "retrieve_evidence":
            payload = json.loads(result["model_visible_content"])
            retrieved_ids.extend(payload.get("evidence_refs", []))
        if call["tool_name"] == "query_evidence_matrix":
            matrix_loaded = True
    return {"last_event_seq": events[-1]["event_seq"] if events else 0, "last_event_sha256": events[-1]["event_sha256"] if events else None, "successful_tool_signatures": signatures, "completed_tool_call_ids": [item["tool_call_id"] for item in results], "retrieved_evidence_ids": list(dict.fromkeys(retrieved_ids)), "retrieved_evidence_count": len(set(retrieved_ids)), "covered_entities": [], "missing_entities": [], "retrieval_calls_used": sum(call["tool_name"] == "retrieve_evidence" and call["tool_call_id"] in {item["tool_call_id"] for item in successful} for call in calls), "retrieval_calls_remaining": None, "tool_calls_used": len(successful), "tool_calls_remaining": None, "evidence_matrix_loaded": matrix_loaded, "approval_status": "not_requested", "allowed_next_actions": [], "no_progress_steps": 0, "steering_used": False}


def render_planner_request(durable_events: list[dict[str, Any]], projected_state: dict[str, Any], allowed_tools: list[dict[str, Any]], *, task: dict[str, Any]) -> dict[str, Any]:
    results = [event["model_visible_content"] for event in durable_events if event["event_type"] == "tool_result"]
    user_payload = {"task_id": task["task_id"], "research_goal_zh": task["task_zh"], "progress_context": {"tool_results": results, "projection": projected_state}}
    messages = [{"role": "system", "content": PLANNER_SYSTEM_PROMPT}, {"role": "user", "content": _canonical(user_payload)}]
    payload = {"messages": messages, "tools": allowed_tools}
    return {"messages": messages, "tools": allowed_tools, "rendered_messages_sha256": _sha(_canonical(messages)), "rendered_tools_sha256": _sha(_canonical(allowed_tools)), "request_sha256": _sha(_canonical(payload))}


def replay_planner_requests(event_log_path: Path, allowed_tools: list[dict[str, Any]], *, task: dict[str, Any]) -> dict[str, Any]:
    events = DurableEventLog(event_log_path, "", "").load_verified_events()
    requests = []
    for event in events:
        if event["event_type"] != "provider_step":
            continue
        boundary = event.get("request_event_seq") or event["event_seq"]
        prior = [item for item in events if item["event_seq"] < boundary]
        rendered = render_planner_request(prior, project_events(prior), allowed_tools, task=task)
        stored = event["request_payload"]
        if _canonical({"messages": rendered["messages"], "tools": rendered["tools"]}) != _canonical(stored):
            raise DurableEventError("canonical_request_replay_mismatch")
        requests.append(rendered)
    return {"external_llm_called": False, "requests": requests}


def run_fake_durable_validation(out_dir: Path) -> dict[str, Any]:
    """Create a deterministic, zero-provider v2 event/replay validation artifact."""
    if out_dir.exists():
        raise DurableEventError("fake durable validation output already exists")
    task = {"task_id": "FAKE01", "task_zh": "验证中文证据工具结果"}
    tools = [{"type": "function", "function": {"name": "retrieve_evidence", "parameters": {"type": "object"}}}]
    log = DurableEventLog.create(out_dir / "durable_events", turn_id="FAKE01:turn:1", task_id="FAKE01", run_identity={"prompt_sha": _sha(PLANNER_SYSTEM_PROMPT), "policy_sha": "fake-policy", "task_set_sha": "fake-task-set", "git_sha": "fake-git"})
    first = render_planner_request(log.load_verified_events(), log.projection(), tools, task=task)
    request_seq = log.record_planner_request({"messages": first["messages"], "tools": first["tools"]})
    log.record_provider_step(step_id="FAKE01:step:1", model="fake", model_call_ordinal=1, request_payload={"messages": first["messages"], "tools": first["tools"]}, request_event_seq=request_seq, tool_calls=[{"tool_call_id": "fake-call-1", "tool_name": "retrieve_evidence", "args": {"query": "evidence"}}], usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    log.record_tool_result("fake-call-1", result_status="success", internal_result={"evidence_refs": ["P1:C1"]}, model_visible_content=_canonical({"evidence_refs": ["P1:C1"], "message": "已检索到证据。"}), verification_status="passed")
    second = render_planner_request(log.load_verified_events(), log.projection(), tools, task=task)
    request_seq = log.record_planner_request({"messages": second["messages"], "tools": second["tools"]})
    log.record_provider_step(step_id="FAKE01:step:2", model="fake", model_call_ordinal=2, request_payload={"messages": second["messages"], "tools": second["tools"]}, request_event_seq=request_seq, tool_calls=[], usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    replay = replay_planner_requests(log.path, tools, task=task)
    summary = {"role": "m8b1a_fake_runtime_validation", "external_llm_called": False, "trace_schema_version": TRACE_SCHEMA_VERSION, "terminal_results_valid": log.validate_terminal_results(), "canonical_request_replay": second["request_sha256"] == replay["requests"][-1]["request_sha256"], "projection": log.projection(), "event_log_sha256": _sha(log.path.read_text(encoding="utf-8"))}
    (out_dir / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "trace_manifest.json").write_text(json.dumps({"durable_event_path": "durable_events/events.jsonl", "event_log_sha256": summary["event_log_sha256"], "external_llm_called": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _synthetic_call_id(step_id: str, ordinal: int, tool_name: str, args_sha256: str) -> str:
    return "synthetic_" + _sha(f"{step_id}:{ordinal}:{tool_name}:{args_sha256}")[:24]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timestamp() -> str:
    return "1970-01-01T00:00:00Z"


def _assert_safe_payload(payload: dict[str, Any]) -> None:
    if _contains_forbidden(payload):
        raise DurableEventError("forbidden content in durable event")


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("role") == "system" and value.get("content") == PLANNER_SYSTEM_PROMPT:
            return False
        return any(_contains_forbidden(key) or _contains_forbidden(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(item) for item in value)
    if isinstance(value, str):
        lowered = value.casefold()
        return any(marker in lowered for marker in ("gold_evidence_summary", "authorization", "api_key", "bearer "))
    return False
